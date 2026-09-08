FROM mcr.microsoft.com/devcontainers/base:ubuntu

# uv: official static binary, no curl|sh
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Claude Code policy: highest precedence, cannot be overridden from ~/.claude or .claude/
RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json

# On first mount of a named volume, podman takes over the ownership of the underlying image directory.
# If /home/vscode/.claude does not exist in the image, the volume belongs to container root and vscode cannot write.
RUN mkdir -p /home/vscode/.claude && chown vscode:vscode /home/vscode/.claude

USER vscode
