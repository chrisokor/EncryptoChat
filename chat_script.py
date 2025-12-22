import sys
from chat_client import ChatClient


if __name__ == '__main__':
    '''
    terminal 1:
    python client_demo.py alice
    terminal 2:
    python client_demo.py bob
    '''

    name = sys.argv[1] if len(sys.argv[1]) > 1 else "alice"
    client = ChatClient(name)

    
    client.register()

    while True:
        command = input(f"{name}> ").strip()
        if command == "inbox":
            client.receive_all()
        elif command.startswith("hi "):
            peer = command.split()[1]
            client.handshake_with(peer)
            client.send_message(peer, f"hello from {name}")
        elif command.startswith("msg "):
            _, peer, *words = command.split()
            if peer not in client.shared_boxes:
                client.handshake_with(peer)
            client.send_message(peer, " ".join(words))
        elif command in ("quit", "exit"):
            break
        else:
            print("commands: 'hi <peer>' to start, 'msg <peer> <text>', 'inbox', 'exit'")

