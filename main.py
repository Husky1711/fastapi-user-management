from fastapi import FastAPI
from routes.login import router as login_router
from utils.loggers import app_logger

app = FastAPI(title="FastAPI User Management", version="1.0.0")

# Include routers
app.include_router(login_router)

@app.get("/hello")
def health_check() -> dict:
    """Health check endpoint"""
    app_logger.info("Health check endpoint accessed", endpoint="/hello")
    return {"message": "Hello World", "status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    app_logger.info("FastAPI application started", event_type="app_startup")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    app_logger.info("FastAPI application shutting down", event_type="app_shutdown")

if __name__ == "__main__":
    import uvicorn 
    app_logger.info("Starting FastAPI server with uvicorn", event_type="uvicorn_startup")
    uvicorn.run("main:app", host="localhost", port=9000, reload=True)