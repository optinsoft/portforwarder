import asyncio
import argparse
from pathlib import Path
import threading

__version__ = "1.0"
__module__ = Path(__file__).stem

async def handle_client(reader, writer, target_host, target_port):
    try:
        target_reader, target_writer = await asyncio.open_connection(target_host, target_port)
        await asyncio.gather(
            relay(reader, target_writer),
            relay(target_reader, writer)
        )
    finally:
        writer.close()

async def relay(reader, writer):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()

def console_input():
    print("Press q + enter to quit")
    while True:
        cmd = input()
        if len(cmd) > 0:
            if "q" == cmd: break

async def start_server(source_host, source_port, target_host, target_port):
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(reader, writer, target_host, target_port),
        source_host, source_port
    )

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    loop = asyncio.get_running_loop()

    try:
        await loop.run_in_executor(None, console_input)
    finally:
        print(f"Serving has finished.")
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{__module__} {__version__}")

    parser.add_argument('--source-host', type=str, required=True, help='Source host to listen on')
    parser.add_argument('--source-port', type=int, required=True, help='Source port to listen on')
    parser.add_argument('--target-host', type=str, required=True, help='Target port to forward connections to')
    parser.add_argument('--target-port', type=int, required=True, help='Target port to forward connections to')

    args = parser.parse_args()

    asyncio.run(start_server(
        args.source_host, 
        args.source_port, 
        args.target_host, 
        args.target_port)
    )
    
