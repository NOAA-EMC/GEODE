# Use noaaepic/rocky9-gcc13.3.1-spack-stack as base image
FROM ghcr.io/noaa-emc/i-jedi:latest

RUN useradd -ms /bin/bash developer

# add some extra Python packages
RUN pip install pytest zarr

# Set working directory
WORKDIR /home/developer

# Switch to the non-root user
USER developer

# Add aliases and colorful prompt
RUN echo 'alias ls="ls --color=auto"' >> ~/.bashrc && \
    echo 'alias ll="ls -alF --color=auto"' >> ~/.bashrc && \
    echo 'export PS1="\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ "' >> ~/.bashrc && \
    echo 'git config --global --add safe.directory /workspaces/GEODE' >> ~/.bashrc && \
    echo 'source /opt/spack-environment/activate.sh' >> ~/.bashrc

# Set default command
CMD ["/bin/bash"]