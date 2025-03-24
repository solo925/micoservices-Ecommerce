from datetime import datetime
import json

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user": request.user.pk if request.user.is_authenticated else None,
            "method": request.method,
            "path": request.path,
            "payload": dict(request.POST) if request.method == "POST" else None
        }
        
        # Send to central logging service
        requests.post("http://logging-service/ingest", json=log_entry)
        
        return self.get_response(request)
