FROM mcr.microsoft.com/devcontainers/base:ubuntu

# uv: official static binary, no curl|sh
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Claude Code policy: highest precedence, cannot be overridden from ~/.claude or .claude/
RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json

# podman übernimmt beim ersten Mounten eines Named Volumes die Besitzrechte des darunterliegenden Image‑Verzeichnisses. 
# Existiert /home/vscode/.claude im Image nicht, gehört das Volume Container‑root und vscode kann nicht schreiben.
RUN mkdir -p /home/vscode/.claude && chown vscode:vscode /home/vscode/.claude

USER vscode
