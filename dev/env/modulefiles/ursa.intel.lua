help([[
Load environment for running the GEODE application with Intel compilers and MPI.
]])

local pkgName    = myModuleName()
local pkgVersion = myModuleVersion()
local pkgNameVer = myModuleFullName()

prepend_path("MODULEPATH", '/contrib/spack-stack/spack-stack-2.1.1/envs/ue-oneapi-2025.3.1/modules/Core')

load("stack-intel-oneapi-compilers/2025.3.1")
load("stack-intel-oneapi-mpi/2021.17")
load("bufr-query/0.0.5")
load("py-netcdf4/1.7.2")
load("py-xarray/2024.7.0")
load("py-wxflow/0.2.0")
load("py-pyyaml/6.0.2")
load("py-requests/2.32.3")
load("py-pip/25.1.1")
load("py-wheel/0.45.1")
