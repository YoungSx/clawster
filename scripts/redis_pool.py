#!/usr/bin/env python3
"""
Redis连接池 - 减少连接开销，提高性能
自主进化：从每操作新建连接改为连接池复用
"""
import socket
import threading
import time
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

class PooledRedisClient:
    """带连接池的Redis客户端 - 自主性能优化"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379,
                 password: Optional[str] = None, db: int = 0,
                 pool_size: int = 5, socket_timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.socket_timeout = socket_timeout
        self.pool_size = pool_size
        self._pool = []
        self._lock = threading.Lock()
        self._max_idle_time = 300  # 5分钟空闲回收
        
    def _create_connection(self):
        """创建新连接"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.socket_timeout)
        sock.connect((self.host, self.port))
        
        # Auth if needed
        if self.password:
            self._send_cmd(sock, ['AUTH', self.password])
        if self.db:
            self._send_cmd(sock, ['SELECT', str(self.db)])
            
        return {
            'socket': sock,
            'created_at': time.time(),
            'last_used': time.time(),
            'in_use': False
        }
    
    def _send_cmd(self, sock, parts: List[str]) -> Any:
        """发送命令并读取响应"""
        # RESP协议编码
        cmd = f'*{len(parts)}\r\n'
        for p in parts:
            cmd += f'${len(p)}\r\n{p}\r\n'
        sock.sendall(cmd.encode())
        
        # 读取响应
        buffer = b''
        while b'\r\n' not in buffer:
            buffer += sock.recv(4096)
        
        line, _ = buffer.split(b'\r\n', 1)
        prefix = line[0:1]
        data = line[1:].decode()
        
        if prefix == b'+':
            return data
        elif prefix == b'-':
            raise Exception(f'Redis error: {data}')
        elif prefix == b':':
            return int(data)
        elif prefix == b'$':
            length = int(data)
            if length < 0:
                return None
            # 读取bulk string
            while len(buffer) < length + 2:
                buffer += sock.recv(4096)
            result = buffer[:length].decode()
            return result
        elif prefix == b'*':
            count = int(data)
            return [self._read_element(sock) for _ in range(count)]
        return None
    
    def _read_element(self, sock):
        """读取数组元素"""
        line = b''
        while not line.endswith(b'\r\n'):
            line += sock.recv(1)
        line = line[:-2]
        
        if line[0:1] == b'$':
            length = int(line[1:])
            if length < 0:
                return None
            data = b''
            while len(data) < length:
                data += sock.recv(length - len(data))
            sock.recv(2)  # \r\n
            return data.decode()
        return line.decode()
    
    @contextmanager
    def get_connection(self):
        """获取连接（上下文管理器）"""
        conn = None
        try:
            with self._lock:
                # 找一个可用连接
                for c in self._pool:
                    if not c['in_use'] and (time.time() - c['last_used']) < self._max_idle_time:
                        c['in_use'] = True
                        c['last_used'] = time.time()
                        conn = c
                        break
                
                # 没有可用连接且池未满，创建新连接
                if conn is None and len(self._pool) < self.pool_size:
                    conn = self._create_connection()
                    conn['in_use'] = True
                    self._pool.append(conn)
            
            yield conn['socket']
        finally:
            if conn:
                conn['in_use'] = False
    
    def execute(self, cmd: List[str]) -> Any:
        """执行命令"""
        with self.get_connection() as sock:
            return self._send_cmd(sock, cmd)
    
    def setex(self, key: str, seconds: int, value: str) -> str:
        result = self.execute(['SETEX', key, str(seconds), value])
        if result != 'OK':
            raise Exception(f'SETEX failed: {result}')
        return result
    
    def get(self, key: str) -> Optional[str]:
        return self.execute(['GET', key])
    
    def hset(self, key: str, field: str, value: str) -> int:
        result = self.execute(['HSET', key, field, value])
        if result is None:
            raise Exception('HSET failed')
        return result
    
    def hgetall(self, key: str) -> Dict[str, str]:
        result = self.execute(['HGETALL', key])
        if not result:
            return {}
        return {result[i]: result[i+1] for i in range(0, len(result), 2)}
    
    def set(self, key: str, value: str, nx: bool = False, 
            xx: bool = False, ex: Optional[int] = None) -> Optional[str]:
        cmd = ['SET', key, value]
        if nx:
            cmd.append('NX')
        if xx:
            cmd.append('XX')
        if ex is not None:
            cmd.extend(['EX', str(ex)])
        return self.execute(cmd)
    
    def delete(self, key: str) -> int:
        result = self.execute(['DEL', key])
        if result is None:
            raise Exception('DELETE failed')
        return result
    
    def keys(self, pattern: str = '*') -> List[str]:
        result = self.execute(['KEYS', pattern])
        return result if result else []
    
    def ttl(self, key: str) -> int:
        result = self.execute(['TTL', key])
        return result if result is not None else -2

# 全局连接池实例
_pool_instance = None
_pool_lock = threading.Lock()

def get_redis_pool(**kwargs) -> PooledRedisClient:
    """获取全局连接池实例（单例模式）"""
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = PooledRedisClient(**kwargs)
    return _pool_instance

if __name__ == '__main__':
    # 测试连接池
    import json
    with open('../config/secrets.json') as f:
        cfg = json.load(f)
    
    pool = get_redis_pool(**cfg['redis'])
    
    print("🚀 连接池性能测试")
    print("="*50)
    
    import time
    start = time.time()
    for i in range(100):
        pool.setex(f'test:pool:{i}', 60, f'value{i}')
    elapsed = time.time() - start
    print(f"100次SETEX: {elapsed*1000:.2f}ms (平均{elapsed*10:.2f}ms/次)")
    
    # 清理
    for i in range(100):
        pool.delete(f'test:pool:{i}')
    
    print("✅ 连接池测试通过!")
