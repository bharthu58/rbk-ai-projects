import { test, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ToolInvocationBadge } from "../ToolInvocationBadge";

afterEach(() => {
  cleanup();
});

// --- str_replace_editor labels ---

test("shows 'Creating <path>' for str_replace_editor create", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "1",
        toolName: "str_replace_editor",
        args: { command: "create", path: "/App.jsx" },
        state: "result",
        result: "ok",
      }}
    />
  );
  expect(screen.getByText("Creating /App.jsx")).toBeDefined();
});

test("shows 'Editing <path>' for str_replace_editor str_replace", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "2",
        toolName: "str_replace_editor",
        args: { command: "str_replace", path: "/components/Card.jsx" },
        state: "result",
        result: "ok",
      }}
    />
  );
  expect(screen.getByText("Editing /components/Card.jsx")).toBeDefined();
});

test("shows 'Editing <path>' for str_replace_editor insert", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "3",
        toolName: "str_replace_editor",
        args: { command: "insert", path: "/App.jsx" },
        state: "call",
      }}
    />
  );
  expect(screen.getByText("Editing /App.jsx")).toBeDefined();
});

test("shows 'Reading <path>' for str_replace_editor view", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "4",
        toolName: "str_replace_editor",
        args: { command: "view", path: "/App.jsx" },
        state: "call",
      }}
    />
  );
  expect(screen.getByText("Reading /App.jsx")).toBeDefined();
});

test("shows 'Reverting <path>' for str_replace_editor undo_edit", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "5",
        toolName: "str_replace_editor",
        args: { command: "undo_edit", path: "/App.jsx" },
        state: "call",
      }}
    />
  );
  expect(screen.getByText("Reverting /App.jsx")).toBeDefined();
});

// --- file_manager labels ---

test("shows 'Renaming <path>' for file_manager rename", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "6",
        toolName: "file_manager",
        args: { command: "rename", path: "/old.jsx", new_path: "/new.jsx" },
        state: "result",
        result: "ok",
      }}
    />
  );
  expect(screen.getByText("Renaming /old.jsx")).toBeDefined();
});

test("shows 'Deleting <path>' for file_manager delete", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "7",
        toolName: "file_manager",
        args: { command: "delete", path: "/App.jsx" },
        state: "result",
        result: "ok",
      }}
    />
  );
  expect(screen.getByText("Deleting /App.jsx")).toBeDefined();
});

// --- Unknown tool fallback ---

test("renders raw toolName for unknown tools", () => {
  render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "8",
        toolName: "some_unknown_tool",
        args: {},
        state: "result",
        result: "ok",
      }}
    />
  );
  expect(screen.getByText("some_unknown_tool")).toBeDefined();
});

// --- State-based indicator ---

test("shows green dot when state is 'result' with a result", () => {
  const { container } = render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "9",
        toolName: "str_replace_editor",
        args: { command: "create", path: "/App.jsx" },
        state: "result",
        result: "ok",
      }}
    />
  );
  const dot = container.querySelector(".bg-emerald-500");
  expect(dot).not.toBeNull();
});

test("shows spinner when state is not 'result'", () => {
  const { container } = render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "10",
        toolName: "str_replace_editor",
        args: { command: "create", path: "/App.jsx" },
        state: "call",
      }}
    />
  );
  const dot = container.querySelector(".bg-emerald-500");
  expect(dot).toBeNull();
  const spinner = container.querySelector(".animate-spin");
  expect(spinner).not.toBeNull();
});

test("shows spinner when state is 'result' but result is null", () => {
  const { container } = render(
    <ToolInvocationBadge
      toolInvocation={{
        toolCallId: "11",
        toolName: "str_replace_editor",
        args: { command: "create", path: "/App.jsx" },
        state: "result",
        result: null,
      }}
    />
  );
  const dot = container.querySelector(".bg-emerald-500");
  expect(dot).toBeNull();
  const spinner = container.querySelector(".animate-spin");
  expect(spinner).not.toBeNull();
});
