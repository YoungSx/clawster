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

    def set(self, key: str, value: str, nx: bool = False, xx: bool = False,
            ex: Optional[int] = None, px: Optional[int] = None) -> Optional[str]:
        """SET key value [NX] [XX] [EX seconds] [PX milliseconds]
        - NX: only set if key doesn't exist
        - XX: only set if key exists
        - EX: expire time in seconds
        - PX: expire time in milliseconds
        Returns: "OK" on success, None if NX/XX condition not met
        """
        cmd = ['SET', key, value]
        if nx:
            cmd.append('NX')
        if xx:
            cmd.append('XX')
        if ex is not None:
            cmd.extend(['EX', str(ex)])
        if px is not None:
            cmd.extend(['PX', str(px)])
        result = self._cmd(cmd)
        return result

    def delete(self, key: str) -> int:
        """Delete a key, returns number of keys deleted"""
        result = self._cmd(['DEL', key])
        if result is None:
            raise Exception(f'DELETE failed: got None')
        return result

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

    # Key commands
    def keys(self, pattern: str = '*') -> List[str]:
        """Find all keys matching the given pattern"""
        result = self._cmd(['KEYS', pattern])
        return result if result is not None else []

    def ttl(self, key: str) -> int:
        """Get remaining TTL of a key in seconds"""
        result = self._cmd(['TTL', key])
        return result if result is not None else -2

    def exists(self, key: str) -> int:
        """Check if key exists (1 if exists, 0 if not)"""
        result = self._cmd(['EXISTS', key])
        return result if result is not None else 0

    # List commands
    def lpush(self, key: str, *values: str) -> int:
        """Push values to the left of a list"""
        return self._cmd(['LPUSH', key] + list(values))

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """Get a range of elements from a list"""
        result = self._cmd(['LRANGE', key, str(start), str(stop)])
        return result if result else []

    def llen(self, key: str) -> int:
        """Get the length of a list"""
        result = self._cmd(['LLEN', key])
        return result if result is not None else 0

    def ltrim(self, key: str, start: int, stop: int) -> str:
        """Trim a list to the specified range"""
        return self._cmd(['LTRIM', key, str(start), str(stop)])

    # Pub/Sub
    def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel"""
        result = self._cmd(['PUBLISH', channel, message])
        return result if result is not None else 0
