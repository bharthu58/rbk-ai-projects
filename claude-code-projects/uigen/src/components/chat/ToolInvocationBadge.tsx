"use client";

import { Loader2 } from "lucide-react";

interface ToolInvocationProps {
  state: string;
  output?: unknown;
  toolName: string;
  input: Record<string, unknown>;
}

interface Props {
  toolInvocation: ToolInvocationProps;
}

function getLabel(toolName: string, input: Record<string, unknown>): string {
  const path = input.path as string | undefined;

  if (toolName === "str_replace_editor" && path) {
    switch (input.command) {
      case "create":
        return `Creating ${path}`;
      case "str_replace":
      case "insert":
        return `Editing ${path}`;
      case "view":
        return `Reading ${path}`;
      case "undo_edit":
        return `Reverting ${path}`;
      default:
        return `Updating ${path}`;
    }
  }

  if (toolName === "file_manager" && path) {
    switch (input.command) {
      case "rename":
        return `Renaming ${path}`;
      case "delete":
        return `Deleting ${path}`;
      default:
        return `Managing ${path}`;
    }
  }

  return toolName;
}

export function ToolInvocationBadge({ toolInvocation }: Props) {
  const { state, output, toolName, input } = toolInvocation;
  const isDone = state === "output-available" && output != null;
  const label = getLabel(toolName, input);

  return (
    <div className="inline-flex items-center gap-2 mt-2 px-3 py-1.5 bg-neutral-50 rounded-lg text-xs font-mono border border-neutral-200">
      {isDone ? (
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
      ) : (
        <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
      )}
      <span className="text-neutral-700">{label}</span>
    </div>
  );
}
