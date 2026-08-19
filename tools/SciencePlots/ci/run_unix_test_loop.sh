#!/usr/bin/env bash
# Copyright notice: you are allowed to use this script as long as you credit the author and all it's contributors on the following list:
# Author: Echedey Luis, June 2026.

# make sure current dir is project tree
# https://stackoverflow.com/questions/3349105/how-can-i-set-the-current-working-directory-to-the-directory-of-the-script-in-ba
cd "$(dirname "$0")"
cd ..

# assert a python virtual environment is active
if [[ ! "$VIRTUAL_ENV" != "" ]]; then
    python -c "import scienceplots"
    if [[ ! $? ]]; then  # unsuccessful import of scienceplots
        echo "scienceplots is not installed. Did you forget to create a venv and install it?"
    fi
fi

# extract current python version
# https://stackoverflow.com/questions/13373249/extract-substring-using-regexp-in-plain-bash
py_version=$(python -V | sed -E -n 's|^Python ([0-9]+\.[0-9]+).*$|\1|p')

py_matplotlib_versions_file="ci/Python${py_version}_matplotlib_versions.txt"

if [ ! -f ${py_matplotlib_versions_file} ]; then
    echo "Matplotlib versions file for Python ${py_version}: '${py_matplotlib_versions_file}' not found; exiting early."
    exit -2
fi

# loop through file lines
# https://stackoverflow.com/questions/1521462/looping-through-the-content-of-a-file-in-bash
# to verify the test file is well-formed
# note the variant of the loop does not generate a subshell, so variables can be updated
# https://unix.stackexchange.com/questions/402750/modify-global-variable-in-while-loop
while read line || [[ -n ${line} ]]; do
    if [[ "${line}" =~ ^\ *#.*$ ]]; then  # needs backslash before space to escape it (else end of RHS is assumed)
        continue  # ignore comments
    elif [[ ! "${line}" =~ ^[0-9]+\.[0-9]+\.[0-9]+.*$ ]]; then
        echo "${py_matplotlib_versions_file} is malformed: \"${line}\". Each line must be of the form ``mayor.minor.patch'' versions."
    fi
done < "${py_matplotlib_versions_file}"

n_tests=0
n_errors=0

# à la previous loop
while read line || [[ -n ${line} ]]; do
    if [[ "${line}" =~ ^\ *#.*$ ]]; then  # needs backslash before space to escape it (else end of RHS is assumed)
        continue  # ignore comments
    elif [[ "${line}" =~ ^[0-9]+\.[0-9]+\.[0-9]+.*$ ]]; then
        ((++n_tests))
        mpl_version=$(echo ${line} | sed -E -n 's|^([0-9]+\.[0-9]+\.[0-9]+).*$|\1|p')
        pip install matplotlib~=${mpl_version}
        pytest
        if [[ ! $? ]]; then  # non-zero exit -> count as error
            ((++n_errors))
        fi
    fi
done < "${py_matplotlib_versions_file}"

if [[ ${n_errors} ]]; then  # 0 is true in bash
    # 0 -> success
    echo "All ${n_tests} tests were successful."
else
    # non-zero -> n of failures
    echo "${n_errors}/${n_tests} failed."
fi

exit ${n_errors}
