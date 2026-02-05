#!/usr/bin/env python3
"""
OpenClaw Distributed - Fixed Redis Client
修复版：移除 or 'OK' 虚假成功问题，添加写入验证
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
            resp.append(f'${len(p)}\r\n{p}\r\n')
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
            # Read the bulk string + trailing \r\n
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
            return [self._read() for _ in range(count)]
        return None

    def _cmd(self, parts: List[str]) -> Any:
        if not self._sock:
            self.connect()
        self._sock.sendall(self._encode(parts))
        return self._read()

    # String commands - 修复：移除 or 'OK'，真实返回结果
    def setex(self, key: str, seconds: int, value: str) -> str:
        result = self._cmd(['SETEX', key, str(seconds), value])
        # 明确检查返回结果
        if result != 'OK':
            raise Exception(f'SETEX failed: expected OK, got {result}')
        return result

    def get(self, key: str) -> Optional[str]:
        return self._cmd(['GET', key])

    # Hash commands - 同样修复
    def hset(self, key: str, field: str, value: str) -> int:
        result = self._cmd(['HSET', key, field, value])
        if result is None:
            raise Exception(f'HSET failed: got None')
        return result

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._cmd(['HGET', key, field])

    def hgetall(self, key: str) -> Dict[str, str]:
        result = self._cmd(['HGETALL', key])
        if not result:
            return {}
        if isinstance(result, list) and len(result) % 2 == 0:
            return {result[i]: result[i+1] for i in range(0, len(result), 2)}
        raise Exception(f'HGETALL returned unexpected format: {result}')

    def hdel(self, key: str, *fields: str) -> int:
        result = self._cmd(['HDEL', key] + list(fields))
        if result is None:
            raise Exception(f'HDEL failed: got None')
        return result
