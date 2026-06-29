#!/usr/bin/env bash
set -euo pipefail

event="$(cat)"

printf '%s' "$event" | jq -r '
  def direct_paths:
    [
      .tool_input.file_path?,
      .tool_input.path?,
      .tool_response.filePath?,
      .tool_response.file_path?
    ];

  def apply_patch_paths:
    if .tool_name == "apply_patch" then
      (
        .tool_input.command // .tool_input.patch // ""
        | split("\n")
        | map(
            if test("^\\*\\*\\* (Add File|Update File|Move to): ") then
              sub("^\\*\\*\\* (Add File|Update File|Move to): "; "")
            else
              empty
            end
          )
      )
    else
      []
    end;

  (direct_paths + apply_patch_paths)[]
  | select(type == "string" and length > 0)
' | awk '!seen[$0]++'
