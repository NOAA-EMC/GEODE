#!/bin/bash
# ==============================================================================
# Environment Setup Script for GEODE / IASI BUFR Plotting on Ursa
# Usage: source load_env.sh
# ==============================================================================

echo "Loading required Spack-stack modules..."

module use ../../obsForge/modulefiles/
module load obsforge/ursa.intel
module load bufr-query/0.0.4
module load py-numpy/1.26.4
module load py-netcdf4/1.7.1.post2
module load py-pandas
module load py-xarray/2024.7.0
module load py-matplotlib/3.7.4
module load py-cartopy/0.24.1
module load imagemagick/7.1.1-29

module list

# 4. Export path to your compiled JEDI bufr Python package (from ObsForge)
#export PYTHONPATH=/scratch3/NCEPDEV/da/Hyundeok.Choi/obsForge/install/lib/python3.11/site-packages:$PYTHONPATH
export PYTHONPATH="/contrib/spack-stack/spack-stack-1.9.2/envs/ue-oneapi-2024.2.1/install/oneapi/2024.2.1/bufr-query-0.0.4-rt5ghyp/lib64/python3.11/site-packages/${PYTHONPATH:+:$PYTHONPATH}"

echo "=============================================================================="
echo "Environment successfully loaded!"
#echo "Python location : $(which python3)"
#echo "PYTHONPATH      : $PYTHONPATH"
echo "=============================================================================="
