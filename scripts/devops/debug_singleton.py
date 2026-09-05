import asyncio
from unittest.mock import patch, AsyncMock

class Singleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def do_work(self):
        print("REAL WORK EXECUTED")
        return "real"

def run_test_brain():
    s = Singleton()
    with patch.object(s, 'do_work', new_callable=AsyncMock) as m:
        m.return_value = "leaked"
    print("dict after teardown:", s.__dict__)

async def run_test_diagram():
    s = Singleton()
    with patch("__main__.Singleton.do_work", new_callable=AsyncMock) as m:
        m.return_value = "mocked"
        res = await s.do_work()
        print("Diagram result:", res)

async def main():
    run_test_brain()
    await run_test_diagram()

if __name__ == '__main__':
    asyncio.run(main())
