# Use noaaepic/rocky9-gcc13.3.1-spack-stack1.9 as base image
FROM noaaepic/rocky9-gcc13.3.1-spack-stack1.9:latest

RUN useradd -ms /bin/bash developer

# Set working directory
WORKDIR /home/developer

# Switch to the non-root user
USER developer

# Set default command
CMD ["/bin/bash"]