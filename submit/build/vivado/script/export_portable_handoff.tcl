# Export the OPEN project, without running synthesis/implementation or hardware actions.
# This standalone file may also be copied to a convenient local launcher location.
namespace eval ss_portable_export {
    proc one {values label} {
        if {[llength $values]!=1} {error "STOP: expected one $label"}
        return [lindex $values 0]
    }
    proc read_text {path} {
        set h [open $path r];fconfigure $h -encoding utf-8
        try {return [read $h]} finally {close $h}
    }
    proc write_text {path text} {
        file mkdir [file dirname $path]
        set h [open $path w];fconfigure $h -encoding utf-8 -translation lf
        try {puts -nonewline $h $text} finally {close $h}
    }
    proc relative {path base} {
        set p [file split [file normalize $path]];set b [file split [file normalize $base]]
        if {[llength $p]<=[llength $b] || ![string equal -nocase [lrange $p 0 [expr {[llength $b]-1}]] $b]} {
            error "STOP: dependency outside project; use Copy File into Project first: $path"
        }
        return [join [lrange $p [llength $b] end] /]
    }
    proc machine_path {text} {
        # Match drive, UNC and common Unix home/workspace absolute paths, including JSON escaping.
        # JSON escapes each relative Windows separator as two backslashes.
        # UNC must begin a path token, not occur halfway through "ip\\name".
        return [regexp -nocase {((^|[^a-z0-9_])[a-z]:[/\\]|(^|[[:space:]"'=\{])\\{2,}[a-z0-9_.-]+\\|(^|[[:space:]"'=\{])/(home|Users|mnt|tmp|opt|workspace|usr|var|Volumes)/)} $text]
    }
    proc check_text {path label} {
        if {[machine_path [read_text $path]]} {
            error "STOP: unresolved machine path in $label; old latest preserved"
        }
    }
    proc strip_path_comments {text} {
        set lines {}
        foreach line [split $text \n] {
            if {[regexp {^\s*#} $line] && [machine_path $line]} {continue}
            lappend lines $line
        }
        return [join $lines \n]
    }
    proc without_utils_cache {text} {
        # Vivado 2025.2 does not expose -ignore_utils in every Tcl Store build.
        # Remove ONLY the known generated utils_1 block from the exported text;
        # never unregister files or change properties of the open user project.
        set lines {};set in_utils 0;set count 0
        foreach line [split $text \n] {
            set line [string trimright $line \r]
            if {$line eq {# Set 'utils_1' fileset object}} {
                if {$in_utils || $count} {error {STOP: unexpected duplicate utils export section}}
                set in_utils 1;incr count;continue
            }
            if {$in_utils} {
                if {[string trim $line] eq {set_property -name "name" -value "utils_1" -objects $obj}} {
                    set in_utils 0
                    lappend lines {# Original utils_1 build cache intentionally omitted.}
                }
                continue
            }
            # The native dependency check lists each cached file on one continued
            # list line. Remove that reference, not arbitrary user .dcp text.
            if {[regexp {^\s*"?\[file normalize "\$\{?origin_dir\}?/[^"\n]*/utils_1/[^"\n]+"\s*\]"?\\\s*$} $line]} {continue}
            # Rebuild from sources; a previous incremental checkpoint is not input.
            if {[regexp {^set_property -name "incremental_checkpoint" -value .* -objects \$obj$} $line]} {
                set line {set_property -name "incremental_checkpoint" -value "" -objects $obj}
            }
            if {[regexp {^set_property -name "auto_incremental_checkpoint" -value .* -objects \$obj$} $line]} {
                set line {set_property -name "auto_incremental_checkpoint" -value "0" -objects $obj}
            }
            lappend lines $line
        }
        if {$in_utils} {error {STOP: unrecognized utils export layout; original project unchanged}}
        set result [join $lines \n]
        if {[regexp {get_filesets\s+utils_1|\$\{?origin_dir\}?/[^"\n]*/utils_1/} $result]} {
            error {STOP: unhandled utils dependency in recipe; old latest preserved}
        }
        if {![info complete $result]} {error {STOP: incomplete portable project Tcl}}
        return $result
    }
    proc portable_bd {text root files} {
        # Vivado emits module-reference fallback imports with absolute paths even
        # when the project recipe is relative. Rebuild each import as a Tcl list.
        set result {}
        foreach line [split [strip_path_comments $text] \n] {
            if {[regexp {^(\s*)import_files -quiet -fileset sources_1 (.+)$} $line -> indent path]} {
                set path [string trim $path]
                if {[string index $path 0] eq "\"" || [string index $path 0] eq "\{"} {
                    set path [string range $path 1 end-1]
                }
                if {[file pathtype $path] eq "absolute"} {
                    set rel [relative $path $root]
                    if {![dict exists $files $rel]} {error "STOP: uncollected BD module source: $rel"}
                    set line "${indent}import_files -quiet -fileset sources_1 \[list \[file join \$::ss_handoff_source [list $rel]\]\]"
                }
            }
            lappend result $line
        }
        return "# Sources are relative to this exported package.\nset ::ss_handoff_source \[file normalize \[file join \[file dirname \[info script\]\] .. payload\]\]\n[join $result \n]"
    }
    proc add_file {path root filesvar} {
        upvar 1 $filesvar files
        set path [file normalize $path]
        set rel [relative $path $root]
        if {![file isfile $path]} {error "STOP: missing dependency: $rel"}
        if {[file type $path] eq "link"} {error "STOP: symbolic dependency: $rel"}
        dict set files $rel $path
    }
    proc include_tree {dir root filesvar} {
        upvar 1 $filesvar files
        relative $dir $root
        foreach p [glob -nocomplain -directory $dir *] {
            if {[file type $p] eq "link"} {error {STOP: symbolic include directory}}
            if {[file isdirectory $p]} {include_tree $p $root files} else {add_file $p $root files}
        }
    }
    proc collect_recipe_inputs {text root filesvar} {
        upvar 1 $filesvar files
        # Native Tcl sometimes references a generated HDL wrapper not returned as
        # a top-level file. Collect its actual file too, without copying caches.
        foreach {whole rel} [regexp -all -inline {\$\{?origin_dir\}?/([^"\]\n]+)} $text] {
            set rel [string trim $rel]
            if {[regexp {[$\[]|^[.]+$} $rel]} {continue}
            if {[string tolower [file extension $rel]] ni {.v .sv .vh .svh .vhd .vhdl .xdc .mem .coe .hex .dat .tcl .bd .xci}} {continue}
            add_file [file join $root $rel] $root files
        }
    }
    proc collect_includes {root filesvar} {
        upvar 1 $filesvar files
        set seen [dict create]
        while {1} {
            set changed 0
            foreach rel [dict keys $files] {
                if {[dict exists $seen $rel]} {continue}
                dict set seen $rel 1;set changed 1
                if {[string tolower [file extension $rel]] ni {.v .sv .vh .svh}} {continue}
                foreach {whole include} [regexp -all -inline {`include\s+"([^"\n]+)"} [read_text [dict get $files $rel]]] {
                    set local [file join [file dirname [dict get $files $rel]] $include]
                    if {[file isfile $local]} {add_file $local $root files;continue}
                    set found 0
                    foreach known [dict keys $files] {
                        if {[string match "*/$include" $known] || $known eq $include} {set found 1;break}
                    }
                    if {!$found} {error "STOP: unresolved RTL include $include in $rel; register/copy its include directory"}
                }
            }
            if {!$changed} {break}
        }
    }
    proc run {} {
        set project [one [get_projects -quiet] {open project}]
        set root [file normalize [get_property DIRECTORY $project]]
        foreach run [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $run]]} {
                error "STOP: active run $run; wait for it to finish"
            }
        }
        # Custom IP repositories need their own source/license collection. Never
        # silently export a recipe referencing a developer's repository directory.
        if {[get_property IP_REPO_PATHS $project] ne {}} {
            error {STOP: custom IP repository configured; collect it explicitly before portable export}
        }
        set files [dict create];set bds {}
        foreach fs [get_filesets -quiet] {
            if {[get_property FILESET_TYPE $fs] eq {Utils}} {continue}
            if {[get_property IP_REPO_PATHS $fs] ne {}} {error {STOP: fileset has a custom IP repository}}
            foreach object [get_files -quiet -norecurse -of_objects $fs] {
                set path [get_property NAME $object]
                # IP/BD generated children are recreated from their registered parent.
                set parent [get_property PARENT_COMPOSITE_FILE $object]
                if {$parent ne {}} {continue}
                if {[string tolower [file extension $path]] in {.dcp .edf .edn .xcix}} {
                    error {STOP: binary source/core container requires explicit portable handling}
                }
                add_file $path $root files
                if {[string equal -nocase [file extension $path] .bd]} {lappend bds $object}
            }
            foreach dir [get_property INCLUDE_DIRS $fs] {
                if {[file pathtype $dir] ne {absolute}} {set dir [file join $root $dir]}
                include_tree $dir $root files
            }
        }
        if {![dict size $files]} {error {STOP: no registered source files}}
        set handoff [file join $root handoff]
        set tag [clock format [clock seconds] -format %Y%m%d_%H%M%S]_[clock clicks]
        set stage [file join $handoff .pending_$tag]
        file mkdir [file join $stage payload];file mkdir [file join $stage bd]
        # Export failures leave only .pending_*; never replace a valid latest.
        set previous_bd [current_bd_design -quiet]
        try {
            foreach bd $bds {
                open_bd_design $bd
                save_bd_design
                set name [file rootname [file tail [get_property NAME $bd]]]
                set target [file join $stage bd ${name}.tcl]
                write_bd_tcl -force $target
                write_text $target [portable_bd [read_text $target] $root $files]
                check_text $target "bd/${name}.tcl"
            }
        } finally {
            if {$previous_bd ne {}} {current_bd_design $previous_bd}
        }
        # Keep native project/fileset/IP/run properties, but use BD files rather
        # than embedding another set of absolute module-reference import commands.
        set recipe [file join $stage recipe.tcl]
        write_project_tcl -force -internal -all_properties \
            -no_copy_sources -use_bd_files -paths_relative_to $root \
            -origin_dir_override . -target_proj_dir ./recreated_project $recipe
        write_text $recipe [without_utils_cache [strip_path_comments [read_text $recipe]]]
        check_text $recipe recipe.tcl
        collect_recipe_inputs [read_text $recipe] $root files
        collect_includes $root files
        foreach rel [lsort [dict keys $files]] {
            set target [file join $stage payload $rel]
            file mkdir [file dirname $target]
            file copy [dict get $files $rel] $target
            check_text $target "payload/$rel"
        }
        write_text [file join $stage project.tcl] {# Run in an empty Vivado session; all input paths follow this package.
if {[llength [get_projects -quiet]]} {error {Close the current project before recreating this package}}
set ss_package [file dirname [file normalize [info script]]]
if {[file exists [file join $ss_package recreated_project]]} {error {recreated_project already exists; use a fresh package copy}}
set ss_old_pwd [pwd]
set ss_saved_vars [dict create]
foreach key {origin_dir_loc argv argc} {
    if {[info exists ::$key]} {dict set ss_saved_vars $key [set ::$key]}
}
try {
    cd $ss_package
    set ::origin_dir_loc [file join $ss_package payload]
    set ::argv {};set ::argc 0
    source [file join $ss_package recipe.tcl]
} finally {
    cd $ss_old_pwd
    foreach key {origin_dir_loc argv argc} {
        if {[dict exists $ss_saved_vars $key]} {set ::$key [dict get $ss_saved_vars $key]} else {unset -nocomplain ::$key}
    }
}
puts {PROJECT_RECREATED_NO_SYNTHESIS_OR_IMPLEMENTATION_STARTED}
}
        set rows {}
        foreach rel [lsort [dict keys $files]] {lappend rows "payload/$rel"}
        write_text [file join $stage source_files.txt] "[join $rows \n]\n"
        write_text [file join $stage README.txt] {PORTABLE SOURCE HANDOFF
project.tcl: full project recreation entry; recipe.tcl: native project properties.
payload/: registered RTL, constraints, memory files, BD and top-level IP configuration.
bd/: separate readable BD/PS/IP Tcl recipes (not an additional build step).
source_files.txt: package-relative source inventory.
Use the same Vivado version. Copy this entire directory to a fresh location.
In an empty Vivado session source project.tcl. Synthesis and implementation are manual.
This export does not include bit/HWH/XSA or prove successful reconstruction/STA.
Unresolved machine paths, external dependencies and binary sources stop export.
}
        write_text [file join $stage PORTABILITY.txt] "TEXT_MACHINE_PATHS=0\nSOURCE_FILES=[dict size $files]\nSOURCE_DEPENDENCIES_COPIED=1\nACTUAL_REBUILD_NOT_RUN=1\n"
        set latest [file join $handoff latest]
        relative $stage $handoff;relative $latest $handoff
        if {[file exists $latest]} {
            set backup [file join $handoff previous_$tag]
            relative $backup $handoff
            file rename $latest $backup
            puts "PREVIOUS_HANDOFF=$backup"
        }
        file rename $stage $latest
        puts "EXPORT_COMPLETE: $latest"
        puts {PORTABLE_PATHS_CHECKED=1 SOURCE_DEPENDENCIES_COPIED=1 HARDWARE_ACTIONS=0}
    }
}
if {![info exists ::ss_portable_export::library_only] || !$::ss_portable_export::library_only} {ss_portable_export::run}
