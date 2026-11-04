import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from service.logger import get_access_logger

access_logger = get_access_logger()

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Lỗi sẽ được xử lý ở Exception Handler toàn cục, nhưng middleware vẫn tính thời gian
            raise e
        finally:
            process_time = time.time() - start_time
            latency_ms = round(process_time * 1000, 2)
            
            # Lấy status_code nếu request thành công
            status = locals().get('status_code', 500)
            
            client_ip = request.client.host if request.client else "unknown"
            
            # Bỏ qua log một số file tĩnh quá ồn ào của NiceGUI nếu cần thiết
            path = request.url.path
            if not path.startswith("/_nicegui"):
                log_msg = f"{client_ip} | {request.method} {path} | Status: {status} | Latency: {latency_ms}ms"
                access_logger.info(log_msg)
        
        return response
