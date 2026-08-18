FROM python:3.11-slim

ARG USERNAME=developer
ARG GSL_LITE_REF=v1.1.0
ARG NCEPLIBS_BUFR_REF=v12.3.0

RUN useradd -ms /bin/bash ${USERNAME}

# Install system dependencies required by BUFR tooling.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      cmake \
      curl \
      ecbuild \
      gfortran \
      git \
      libeckit-dev \
      libeigen3-dev \
      libnetcdf-c++4-dev \
      libnetcdf-dev \
      libopenmpi-dev \
      libomp-dev \
      pybind11-dev \
      openmpi-bin && \
    rm -rf /var/lib/apt/lists/*

# Install gsl-lite headers and NCEPLIBS-bufr from source.
RUN git clone --branch "${GSL_LITE_REF}" --depth 1 https://github.com/gsl-lite/gsl-lite.git /tmp/gsl-lite && \
    install -d /usr/local/include && \
    cp -r /tmp/gsl-lite/include/gsl /usr/local/include/ && \
    rm -rf /tmp/gsl-lite

RUN git clone --branch "${NCEPLIBS_BUFR_REF}" --depth 1 https://github.com/NOAA-EMC/NCEPLIBS-bufr.git /tmp/NCEPLIBS-bufr && \
    cmake -S /tmp/NCEPLIBS-bufr -B /tmp/NCEPLIBS-bufr/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local && \
    cmake --build /tmp/NCEPLIBS-bufr/build -j"$(nproc)" && \
    cmake --install /tmp/NCEPLIBS-bufr/build && \
    rm -rf /tmp/NCEPLIBS-bufr && \
    ldconfig

# Install Python dependencies used by this repository.
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir \
      pytest==9.1.1 \
      ruff==0.16.3 \
      pywis-pubsub==0.13.0 \
      requests==2.34.2 \
      icechunk==2.1.2 \
      pybind11==3.0.1 \
      wxflow==0.4.2

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
