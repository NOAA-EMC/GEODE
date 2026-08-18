FROM python:3.11-slim

ARG USERNAME=developer

RUN useradd -ms /bin/bash ${USERNAME}

# Install Python dependencies used by this repository.
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir pytest ruff pywis-pubsub requests

# Set working directory
WORKDIR /home/${USERNAME}

# Switch to the non-root user
USER ${USERNAME}

# Add aliases and colorful prompt
RUN echo 'alias ls="ls --color=auto"' >> ~/.bashrc && \
    echo 'alias ll="ls -alF --color=auto"' >> ~/.bashrc && \
    echo 'export PS1="\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ "' >> ~/.bashrc && \
    echo 'git config --global --add safe.directory /workspaces/GEODE' >> ~/.bashrc

# Set default command
CMD ["/bin/bash"]
