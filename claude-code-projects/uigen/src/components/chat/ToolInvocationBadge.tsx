"use client";

import { Loader2 } from "lucide-react";

interface ToolInvocation {
  state: string;
  result?: unknown;
  toolName: string;
  args: Record<string, unknown>;
}

interface Props {
  toolInvocation: ToolInvocation;
}

function getLabel(toolName: string, args: Record<string, unknown>): string {
  const path = args.path as string | undefined;

  if (toolName === "str_replace_editor" && path) {
    switch (args.command) {
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
    switch (args.command) {
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
  const { state, result, toolName, args } = toolInvocation;
  const isDone = state === "result" && result != null;
  const label = getLabel(toolName, args);

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
