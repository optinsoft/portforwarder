import asyncio

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

async def start_server(source_host, source_port, target_host, target_port, duration):
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(reader, writer, target_host, target_port),
        source_host, source_port
    )

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    try:
        await asyncio.sleep(duration)
    finally:
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    source_host = '192.168.1.118'  # Source host to listen on
    source_port = 8000  # Source port to listen on
    target_host = '127.0.0.1'  # Target host to forward connections to
    target_port = 8888  # Target port to forward connections to
    duration = 600  # 10 minutes in seconds

    asyncio.run(start_server(source_host, source_port, target_host, target_port, duration))
