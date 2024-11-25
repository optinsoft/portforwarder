import asyncio
import argparse
from pathlib import Path
import threading
import os
import random
from time import time
from datetime import datetime

__version__ = "1.3"
__module__ = Path(__file__).stem

targets_dict = dict()

async def do_forwarding(reader, writer, target_host, target_port):
    target_reader, target_writer = await asyncio.open_connection(target_host, target_port)
    await asyncio.gather(
        relay(reader, target_writer),
        relay(target_reader, writer)
    )

def check_port_string(s):
    return s.isdigit() and (int(s) in range(1, 65535))

async def handle_client(reader, writer, source_port, target_host, target_port, target_file, allowed_ip_list, allow_any_ip, max_client_target_age):
    try:
        client_ip = None
        try:
            client_ip = writer.get_extra_info('peername')[0]
            print(f"{datetime.now()} [{client_ip} -> {source_port}] Client connected")
            if not allow_any_ip:
                if not client_ip in allowed_ip_list:
                    print(f"{datetime.now()} [{client_ip} -> {source_port}] Client denied")
                    return
            if target_host:
                await do_forwarding(reader, writer, target_host, target_port, allowed_ip_list, allow_any_ip)
            else:
                client_ip_source_port = f"{client_ip}:{source_port}"
                (host, port, first_used_at) = targets_dict[client_ip_source_port] if client_ip_source_port in targets_dict else (None, None, None)
                if host and time() < first_used_at + max_client_target_age:
                    print(f"{datetime.now()} [{client_ip} -> {source_port}] Using cached target: {host}:{port}")
                    await do_forwarding(reader, writer, host, port)
                else:
                    lines = open(target_file).read().splitlines()
                    targets = list(filter(None, lines))
                    random_target = random.choice(targets)            
                    target_host_port = random_target.split(':')
                    if (len(target_host_port) >= 2) and target_host_port[0] and check_port_string(target_host_port[1]):
                        host = target_host_port[0]
                        if host.startswith("#") or host.startswith("+") or host.startswith("*"):
                            host = host[1:]
                        port = int(target_host_port[1])
                        targets_dict[client_ip_source_port] = (host, port, time())
                        print(f"{datetime.now()} [{client_ip} -> {source_port}] New target from file: {host}:{port}")
                        await do_forwarding(reader, writer, host, port)
                    else:
                        print(f"Invalid target: {random_target}")
        finally:
            writer.close()
            if client_ip is not None:
                print(f"{datetime.now()} [{client_ip} -> {source_port}] Client disconnected")
    except Exception as e:
        print(f"{datetime.now()} Exception", e)
    
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

async def start_server(source_host, source_port, target_host, target_port, target_file, allowed_ip_list, allow_any_ip, max_client_target_age):
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(reader, writer, source_port, target_host, target_port, target_file, allowed_ip_list, allow_any_ip, max_client_target_age),
        source_host, source_port
    )

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")

    return (server, addr)

async def wait_for_quit():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, console_input)

async def close_server(server, addr):
    print(f"Serving on {addr} has finished.")
    server.close()
    await server.wait_closed()

def next_port_from_range(ports_range):
    for s in ports_range.split(';'):
        s = s.strip()        
        if s:
            (a, b, *x) = s.split('-') + [s]
            if (check_port_string(a) and check_port_string(b)):
                for p in range(int(a), int(b)+1):
                    yield int(p)

async def main(source_host, source_port, target_host, target_port, target_file, allowed_ip_list, allow_any_ip, max_client_target_age):
    servers = []
    try:
        servers = await asyncio.gather(*[start_server(
            source_host, port, target_host, target_port, target_file, allowed_ip_list, allow_any_ip, max_client_target_age
        ) for port in next_port_from_range(str(source_port))])
        await wait_for_quit()

    finally:
        await asyncio.gather(*[close_server(server, addr) for (server, addr) in servers])

def validate_file(f):
    if not os.path.exists(f):
        raise argparse.ArgumentTypeError("{0} does not exist".format(f))
    return f

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{__module__} {__version__}")

    parser.add_argument('--source-host', type=str, required=True, help='Source host to listen on')
    parser.add_argument('--source-port', type=str, required=True, help='Source port or ports range to listen on')
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument('--target-host', type=str, help='Target port to forward connections to')
    target_group.add_argument('--target-file', type=validate_file, help="Targets file path", metavar="FILE")
    parser.add_argument('--target-port', type=int, help='Target port to forward connections to')
    parser.add_argument('--max-target-age', type=int, nargs='?', const=1, default=600, help='Cached target expires after MAX_TARGET_AGE seconds')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--allow-ip', nargs="+", type=str, help='List of allowed IP addresses')
    group.add_argument('--allow-any-ip', action='store_true', help='Allow access from any IP address')

    args = parser.parse_args()

    if args.target_host and (args.target_port is None):
        parser.error("--target-host required --target-port")

    asyncio.run(main(
        args.source_host, 
        args.source_port,
        args.target_host, 
        args.target_port,
        args.target_file,
        args.allow_ip,
        args.allow_any_ip,
        args.max_target_age)
    )
