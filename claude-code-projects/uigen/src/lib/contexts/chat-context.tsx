"use client";

import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
  useRef,
  ChangeEvent,
  FormEvent,
} from "react";
import { useChat as useAIChat } from "@ai-sdk/react";
import { DefaultChatTransport, UIMessage } from "ai";
import { useFileSystem } from "./file-system-context";
import { setHasAnonWork } from "@/lib/anon-work-tracker";

interface ChatContextProps {
  projectId?: string;
  initialMessages?: UIMessage[];
}

interface ChatContextType {
  messages: UIMessage[];
  input: string;
  handleInputChange: (e: ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e: FormEvent<HTMLFormElement>) => void;
  status: string;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({
  children,
  projectId,
  initialMessages = [],
}: ChatContextProps & { children: ReactNode }) {
  const { fileSystem, handleToolCall } = useFileSystem();
  const appliedToolCalls = useRef(new Set<string>());
  const [input, setInput] = useState("");
  const fileSystemRef = useRef(fileSystem);
  fileSystemRef.current = fileSystem;

  const {
    messages,
    sendMessage,
    status,
  } = useAIChat({
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: "/api/chat",
      body: () => ({
        files: fileSystemRef.current.serialize(),
        projectId,
      }),
    }),
  });

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage({ text: input });
    setInput("");
  };

  // Apply tool calls to the client file system as they arrive in the message stream.
  useEffect(() => {
    for (const message of messages) {
      if (!message.parts) continue;
      for (const part of message.parts) {
        const anyPart = part as any;
        const isToolPart =
          part.type === "dynamic-tool" ||
          (typeof part.type === "string" && part.type.startsWith("tool-"));
        if (isToolPart && anyPart.state !== "input-streaming") {
          const toolCallId = anyPart.toolCallId;
          if (!appliedToolCalls.current.has(toolCallId)) {
            appliedToolCalls.current.add(toolCallId);
            const toolName =
              part.type === "dynamic-tool"
                ? anyPart.toolName
                : part.type.slice(5);
            handleToolCall({ toolName, args: anyPart.input });
          }
        }
      }
    }
  }, [messages, handleToolCall]);

  // Track anonymous work
  useEffect(() => {
    if (!projectId && messages.length > 0) {
      setHasAnonWork(messages, fileSystem.serialize());
    }
  }, [messages, fileSystem, projectId]);

  return (
    <ChatContext.Provider
      value={{
        messages,
        input,
        handleInputChange,
        handleSubmit,
        status,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
}
