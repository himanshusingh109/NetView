"""
TCP Client/Server Echo Benchmark Module for NetView.
Demonstrates socket programming (socket.bind, socket.listen, socket.accept, socket.connect, socket.send, socket.recv)
for the Client/Server syllabus requirement.
"""
import socket
import threading
import time
from typing import Dict, Any, Optional


class EchoServer:
    """
    Lightweight, thread-safe TCP Echo Server.
    Binds to a loopback address, listens for incoming connections,
    echoes received packets back to the client, and supports clean shutdown.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9999):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self._is_running = threading.Event()
        self._server_thread: Optional[threading.Thread] = None
        self.actual_port = port
        self.error_message: Optional[str] = None

    def start(self) -> bool:
        """
        Starts the TCP Echo Server on a background daemon thread.
        Returns True if binding and listening succeeded, False otherwise.
        """
        if self._is_running.is_set():
            return True

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow address reuse to prevent TIME_WAIT bind errors
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Set a 1-second timeout so the accept loop can check the stop event
            self.server_socket.settimeout(1.0)
            self.server_socket.bind((self.host, self.port))
            self.actual_port = self.server_socket.getsockname()[1]
            self.server_socket.listen(5)

            self._is_running.set()
            self._server_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._server_thread.start()
            self.error_message = None
            return True

        except OSError as e:
            self.error_message = f"Port bind failure ({self.host}:{self.port}): {e.strerror or str(e)}"
            self.stop()
            return False

    def _listen_loop(self):
        """Internal accept loop running inside the background thread."""
        while self._is_running.is_set() and self.server_socket:
            try:
                client_sock, client_addr = self.server_socket.accept()
                # Handle each client in a short worker thread
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except (OSError, socket.error):
                break

    def _handle_client(self, client_sock: socket.socket):
        """Receives data from a client and echoes it back verbatim."""
        try:
            client_sock.settimeout(3.0)
            data = client_sock.recv(4096)
            if data:
                # Echo data back
                client_sock.sendall(data)
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def stop(self):
        """Stops the echo server and closes listening sockets."""
        self._is_running.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

    @property
    def is_running(self) -> bool:
        return self._is_running.is_set()


class EchoClient:
    """
    Test Client connecting to the TCP Echo Server.
    Sends a test payload, verifies the response, and measures round-trip time.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9999, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def test_echo(self, payload: bytes = b"NETVIEW_ECHO_PROBE_TEST_PAYLOAD") -> Dict[str, Any]:
        """
        Connects to the server, sends payload, verifies echo, and measures latency.

        Returns:
            dict: {
                "success": bool,
                "rtt_ms": Optional[float],
                "bytes_sent": int,
                "bytes_received": int,
                "verified": bool,
                "error": Optional[str]
            }
        """
        result: Dict[str, Any] = {
            "success": False,
            "rtt_ms": None,
            "bytes_sent": 0,
            "bytes_received": 0,
            "verified": False,
            "error": None,
        }

        client_socket = None
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(self.timeout)

            # High precision start timer
            t_start = time.perf_counter()

            client_socket.connect((self.host, self.port))
            client_socket.sendall(payload)
            result["bytes_sent"] = len(payload)

            received = client_socket.recv(len(payload) + 1024)
            t_end = time.perf_counter()

            result["bytes_received"] = len(received)
            result["rtt_ms"] = round((t_end - t_start) * 1000.0, 2)
            result["verified"] = (received == payload)

            if result["verified"]:
                result["success"] = True
            else:
                result["error"] = "Payload echo mismatch (integrity failure)"

        except socket.timeout:
            result["error"] = f"Connection or echo timed out ({self.timeout}s)"
        except ConnectionRefusedError:
            result["error"] = f"Connection refused at {self.host}:{self.port} (Server not running)"
        except Exception as e:
            result["error"] = f"Client socket error: {str(e)}"
        finally:
            if client_socket:
                try:
                    client_socket.close()
                except Exception:
                    pass

        return result
