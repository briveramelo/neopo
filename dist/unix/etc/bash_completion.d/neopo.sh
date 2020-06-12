# Neopo tab completion function

_project() { 
    local _projects
    _projects=$($1 projects)
    COMPREPLY=($(compgen -W  "$_projects" -- "$cur"))
}

_get-versions() {
    local _versions
    _versions=$($1 list-versions)
    COMPREPLY=($(compgen -W  "$_versions" -- "$cur"))
}

_run() {
    local _targets
    _targets=$($1 targets)
    COMPREPLY=($(compgen -W  "$_targets" -- "$cur"))
}

_configure() {
    local _platforms
    _platforms=$($1 platforms)
    COMPREPLY=($(compgen -W  "$_platforms" -- "$cur"))
}

_neopo() {
    local _options _executable cur prev prev1 prev2
    
    _executable="${COMP_WORDS[0]}"
    _options="$($_executable options)"

    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD - 1]}"
    prev1="${COMP_WORDS[COMP_CWORD - 2]}"
    prev2="${COMP_WORDS[COMP_CWORD - 3]}"

    if [ "$COMP_CWORD" == 1 ]; then
        COMPREPLY=($(compgen -W "$_options" -- "$cur"))
        return 0
    fi

    if [ "$prev1" == "run" ]; then
        _project $_executable
        return 0
    fi

    if [ "$prev1" == "configure" ]; then
        _get-versions $_executable
        return 0
    fi

    if [ "$prev2" == "configure" ]; then
        _project $_executable
        return 0
    fi

    case "$prev" in
    create|compile|build|flash|flash-all|clean)
        _project $_executable;;
    run)
       _run $_executable;;
    configure)
        _configure $_executable;;
    get)
        _get-versions $_executable;;
    esac
}

# Apply the _neopo completion function
complete -F _neopo neopo