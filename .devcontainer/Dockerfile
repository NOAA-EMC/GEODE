FROM python:3.11-slim

ARG USERNAME=developer

RUN useradd -ms /bin/bash ${USERNAME}

# Install system dependencies required by BUFR tooling.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      ecbuild \
      gfortran \
      libeckit-dev \
      libeigen3-dev \
      libnetcdf-c++4-dev \
      libnetcdf-dev \
      libopenmpi-dev \
      libomp-dev \
      openmpi-bin && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies used by this repository.
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir pytest ruff pywis-pubsub requests icechunk wxflow

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
