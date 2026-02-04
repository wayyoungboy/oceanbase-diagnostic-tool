#!/usr/bin/env bash
# Get current effective user information
CURRENT_USER_ID=$(id -u)

# Determine if the script is executed via sudo (not simply based on SUDO_USER)
IS_SUDO_EXECUTED=0
if [ "$CURRENT_USER_ID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
    IS_SUDO_EXECUTED=1
else
    IS_SUDO_EXECUTED=0
fi

# Set user and home directory
if [ $IS_SUDO_EXECUTED -eq 1 ]; then
    # It was executed via sudo, use the original user
    CURRENT_USER_NAME="$SUDO_USER"
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    # Otherwise, use the current user
    CURRENT_USER_NAME=$(id -un)
    USER_HOME="$HOME"
fi

echo "CURRENT_USER_NAME = $CURRENT_USER_NAME"
echo "USER_HOME = $USER_HOME"

if [ -z "$USER_HOME" ]; then
    echo "Error: Could not determine home directory for current user."
    exit 1
fi

if [[ $# == 1 && $1 == "-f" ]]; then
    FORCE_DEPLOY="1"
else
    FORCE_DEPLOY="0"
fi

WORK_DIR=$(readlink -f "$(dirname ${BASH_SOURCE[0]})")

if [ ${OBDIAG_HOME} ]; then
    OBDIAG_HOME=${OBDIAG_HOME}
else
    OBDIAG_HOME="${USER_HOME}/.obdiag"
fi

mkdir -p ${OBDIAG_HOME} && cd ${OBDIAG_HOME}
mkdir -p ${OBDIAG_HOME}/check
mkdir -p ${OBDIAG_HOME}/log
mkdir -p ${OBDIAG_HOME}/display

# Clean rca old *scene.py files
find ${OBDIAG_HOME}/rca -maxdepth 1 -name "*_scene.py" -type f -exec rm -f {} + 2>/dev/null

\cp -rf ${WORK_DIR}/plugins/*  ${OBDIAG_HOME}/
\cp -rf ${WORK_DIR}/conf/ai.yml.example ${OBDIAG_HOME}/ai.yml.example
\cp -rf ${WORK_DIR}/example ${OBDIAG_HOME}/

bashrc_file=~/.bashrc
if [ -e "$bashrc_file" ]; then
  ALIAS_OBDIAG_EXIST=$(grep "alias obdiag='sh" ~/.bashrc | head -n 1)
  if [[ "${ALIAS_OBDIAG_EXIST}" != "" ]]; then
      echo "need update obdiag alias"
      echo "alias obdiag='obdiag'" >> ~/.bashrc
  fi
fi

# DEPRECATED: Old static completion script - now using built-in obdiag complete command
# source  ${WORK_DIR}/init_obdiag_cmd.sh

cd -
output_file=${OBDIAG_HOME}/version.yaml
version_line=$(obdiag --version 2>&1 | grep -oP 'OceanBase Diagnostic Tool: \K[\d.]+')
if [ -n "$version_line" ]; then
    content="obdiag_version: \"$version_line\""

    # Write or update the version information to the file
    echo "$content" > "$output_file"
    
    echo "obdiag version information has been successfully written to $output_file"
else
    echo "failed to retrieve obdiag version information."
fi

# Install completion using built-in completion command
# Define completion function inline (no need for separate script file)
if command -v obdiag >/dev/null 2>&1; then
    # Try to install to system directory
    if [ -d "/etc/bash_completion.d" ] && [ -w "/etc/bash_completion.d" ]; then
        cat > /etc/bash_completion.d/obdiag << 'COMPLETION_EOF'
#!/usr/bin/env bash
# obdiag completion using built-in complete command
_obdiag_completion() {
    local cur_word="${COMP_WORDS[COMP_CWORD]}"
    export COMP_LINE="${COMP_LINE}"
    export COMP_POINT="${COMP_POINT}"
    export COMP_CWORD="${COMP_CWORD}"
    local completions=$(obdiag complete 2>/dev/null)
    COMPREPLY=($(compgen -W "$completions" -- "$cur_word"))
}
complete -F _obdiag_completion obdiag
COMPLETION_EOF
        chmod 644 /etc/bash_completion.d/obdiag 2>/dev/null && \
        echo "Completion installed to /etc/bash_completion.d/obdiag"
    else
        # Fallback to user bashrc
        if [ -f ~/.bashrc ] && ! grep -q "_obdiag_completion" ~/.bashrc; then
            cat >> ~/.bashrc << 'COMPLETION_EOF'

# obdiag completion using built-in complete command
_obdiag_completion() {
    local cur_word="${COMP_WORDS[COMP_CWORD]}"
    export COMP_LINE="${COMP_LINE}"
    export COMP_POINT="${COMP_POINT}"
    export COMP_CWORD="${COMP_CWORD}"
    local completions=$(obdiag complete 2>/dev/null)
    COMPREPLY=($(compgen -W "$completions" -- "$cur_word"))
}
complete -F _obdiag_completion obdiag
COMPLETION_EOF
            echo "Completion added to ~/.bashrc"
        fi
    fi
fi

chown -R ${CURRENT_USER_NAME}: ${OBDIAG_HOME}

echo "Init obdiag finished"
