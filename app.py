import shlex
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import tickets as core

app = FastAPI(title="AI Ticket CLI")

BASE_DIR = Path(__file__).resolve().parent


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/command")
def execute_command(request: CommandRequest):
    try:
        parts = shlex.split(request.command)
    except ValueError:
        return {"output": "Invalid command syntax."}

    if not parts:
        return {"output": "Enter a command. Type help to see options."}

    command = parts[0].lower()

    # Help
    if command == "help" and len(parts) == 1:
        return {
            "output": (
                "Available commands:\n"
                "help       Show available commands\n"
                "list       List saved tickets\n"
                "create     Create a ticket through guided prompts\n"
                "analyze    Analyze a ticket through guided prompts\n"
                "clear      Clear the terminal display\n"
                "\n"
                "AI providers: gemini, groq, openrouter"
            )
        }

    # Clear terminal
    if command == "clear" and len(parts) == 1:
        return {"output": "Terminal cleared.", "clear": True}

    # List tickets
    if command == "list" and len(parts) == 1:
        try:
            saved = core.load_tickets()
        except (OSError, ValueError):
            return {"output": "Could not read tickets.json."}

        if not saved:
            return {"output": "No tickets found."}

        lines = [
            f"{t.get('id', '?')} | {t.get('title', 'Untitled')}"
            for t in saved
        ]

        return {"output": "\n".join(lines)}

    # Create ticket
    if command == "create":
        raw = request.command[len(parts[0]):].strip()

        if "|" not in raw:
            return {
                "output": (
                    "Usage: create TITLE | DESCRIPTION\n"
                    "Example: create Wi-Fi issue | Laptop cannot connect."
                )
            }

        title, description = (
            piece.strip() for piece in raw.split("|", 1)
        )

        if not title or not description:
            return {"output": "Title and description cannot be empty."}

        try:
            saved = core.load_tickets()
            ticket_id = core.generate_ticket_id(saved)

            saved.append({
                "id": ticket_id,
                "title": title,
                "description": description
            })

            core.save_tickets(saved)

        except (OSError, ValueError):
            return {"output": "Could not save the ticket."}

        return {"output": f"Ticket {ticket_id} created successfully."}

    # Analyze ticket
    if command == "analyze" and len(parts) == 3:
        ticket_id = parts[1].upper()

        provider_choice = {
            "gemini": "1",
            "groq": "2",
            "openrouter": "3"
        }.get(parts[2].lower())

        if provider_choice is None:
            return {
                "output": "Choose a provider: gemini, groq, or openrouter."
            }

        try:
            saved = core.load_tickets()
        except (OSError, ValueError):
            return {"output": "Could not read tickets.json."}

        ticket = next(
            (t for t in saved if t.get("id") == ticket_id),
            None
        )

        if ticket is None:
            return {"output": f"Ticket {ticket_id} was not found."}

        provider_name, provider_function = core.PROVIDERS[provider_choice]
        result = provider_function(ticket["description"])

        if result["success"]:
            return {
                "output": (
                    f"AI Analysis — {provider_name}\n\n"
                    f"{result['analysis']}"
                )
            }

        return {"output": result.get("error") or "Analysis failed."}

    # Unknown command
    return {
        "output": (
            f"Unknown command: {command}\n"
            "Type help to see available commands."
        )
    }