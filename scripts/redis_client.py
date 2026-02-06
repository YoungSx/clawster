#!/usr/bin/env python3
"""
OpenClaw Distributed - Unified Redis Client
整合版：支持原子操作、Lua 脚本及稳健的错误处理
"""
import socket
from typing import Optional, Dict, List, Any, Union

class RedisClient:
    """Minimal Redis client using socket (no external dependencies)"""
    CRLF = b'\r\n'

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 password: Optional[str] = None, db: int = 0,
                 decode_responses: bool = True, socket_timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.decode_responses = decode_responses
        self.socket_timeout = socket_timeout
        self._sock: Optional[socket.socket] = None
        self._buffer = b''

    def connect(self) -> bool:
        """Connect to Redis"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.socket_timeout)
        self._sock.connect((self.host, self.port))

        if self.password:
            result = self._cmd(['AUTH', self.password])
            if result != 'OK':
                raise Exception(f'AUTH failed: {result}')

        if self.db:
            result = self._cmd(['SELECT', str(self.db)])
            if result != 'OK':
                raise Exception(f'SELECT failed: {result}')

        return True

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def _encode(self, parts: List[str]) -> bytes:
        resp = [f'*{len(parts)}\r\n']
        for p in parts:
            p_str = str(p)
            resp.append(f'${len(p_str.encode())}\r\n{p_str}\r\n')
        return ''.join(resp).encode()

    def _read(self) -> Any:
        while self.CRLF not in self._buffer:
            data = self._sock.recv(4096)
            if not data:
                raise Exception('Connection closed by server')
            self._buffer += data

        line, self._buffer = self._buffer.split(self.CRLF, 1)
        prefix, data = line[0:1], line[1:]

        if prefix == b'+':
            return data.decode() if self.decode_responses else data
        elif prefix == b'-':
            error_msg = data.decode()
            raise Exception(f'Redis error: {error_msg}')
        elif prefix == b':':
            return int(data)
        elif prefix == b'$':
            length = int(data)
            if length < 0:
                return None
            while len(self._buffer) < length + 2:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise Exception('Connection closed while reading bulk data')
                self._buffer += chunk
            result = self._buffer[:length]
            self._buffer = self._buffer[length+2:]
            return result.decode() if self.decode_responses else result
        elif prefix == b'*':
            count = int(data)
            if count < 0:
                return None
            return [self._read() for _ in range(count)]
        return None

    def _cmd(self, parts: List[Any]) -> Any:
        if not self._sock:
            self.connect()
        self._sock.sendall(self._encode([str(p) for p in parts]))
        return self._read()

    # --- Lua Scripting ---
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        """Execute Lua script: EVAL script numkeys key1 key2 ... arg1 arg2 ..."""
        return self._cmd(['EVAL', script, str(numkeys)] + list(keys_and_args))

    # --- String commands ---
    def get(self, key: str) -> Optional[str]:
        return self._cmd(['GET', key])

    def set(self, key: str, value: str, nx: bool = False, xx: bool = False,
            ex: Optional[int] = None, px: Optional[int] = None) -> Optional[str]:
        cmd = ['SET', key, value]
        if nx: cmd.append('NX')
        if xx: cmd.append('XX')
        if ex is not None: cmd.extend(['EX', str(ex)])
        if px is not None: cmd.extend(['PX', str(px)])
        return self._cmd(cmd)

    def delete(self, *keys: str) -> int:
        result = self._cmd(['DEL'] + list(keys))
        return result if result is not None else 0

    def ttl(self, key: str) -> int:
        result = self._cmd(['TTL', key])
        return result if result is not None else -2

    # --- Hash commands ---
    def hset(self, key: str, field: str, value: str) -> int:
        return self._cmd(['HSET', key, field, value])

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._cmd(['HGET', key, field])

    def hgetall(self, key: str) -> Dict[str, str]:
        result = self._cmd(['HGETALL', key])
        if not result: return {}
        return {result[i]: result[i+1] for i in range(0, len(result), 2)}

    # --- List commands ---
    def lpush(self, key: str, *values: str) -> int:
        return self._cmd(['LPUSH', key] + list(values))

    def ltrim(self, key: str, start: int, stop: int) -> str:
        return self._cmd(['LTRIM', key, str(start), str(stop)])

    def publish(self, channel: str, message: str) -> int:
        return self._cmd(['PUBLISH', channel, message])
