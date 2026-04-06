def intake_thread_ckpt(client_thread_id: str) -> str:
    return f"inbox:{client_thread_id}"


def assist_thread_ckpt(
    department: str,
    ticket_id: str,
    employee_id: str,
    client_thread_id: str,
) -> str:
    return f"assist:{department}:{ticket_id}:{employee_id}:{client_thread_id}"
