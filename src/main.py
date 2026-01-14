import asyncio
import sys

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.api:create_app",
                host="localhost",port=10900,factory=True)