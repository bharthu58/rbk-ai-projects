import { anthropic } from "@ai-sdk/anthropic";
import { LanguageModel } from "ai";

const MODEL = "claude-haiku-4-5";

type V2StreamPart =
  | { type: "stream-start"; warnings: never[] }
  | { type: "text-start"; id: string }
  | { type: "text-delta"; id: string; delta: string }
  | { type: "text-end"; id: string }
  | { type: "tool-input-start"; id: string; toolName: string }
  | { type: "tool-input-delta"; id: string; delta: string }
  | { type: "tool-input-end"; id: string }
  | { type: "tool-call"; toolCallId: string; toolName: string; input: string }
  | { type: "finish"; finishReason: { unified: string; raw: string }; usage: { inputTokens: { total: number }; outputTokens: { total: number } } };

export class MockLanguageModel {
  readonly specificationVersion = "v3" as const;
  readonly provider = "mock";
  readonly modelId: string;
  readonly supportedUrls = {};

  constructor(modelId: string) {
    this.modelId = modelId;
  }

  private async delay(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private extractUserPrompt(messages: any[]): string {
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];
      if (message.role === "user") {
        const content = message.content;
        if (Array.isArray(content)) {
          return content
            .filter((part: any) => part.type === "text")
            .map((part: any) => part.text)
            .join(" ");
        } else if (typeof content === "string") {
          return content;
        }
      }
    }
    return "";
  }

  private getToolMessageCount(messages: any[]): number {
    return messages.filter((m) => m.role === "tool").length;
  }

  private async *generateMockStream(
    messages: any[],
    userPrompt: string
  ): AsyncGenerator<V2StreamPart> {
    const toolMessageCount = this.getToolMessageCount(messages);

    const promptLower = userPrompt.toLowerCase();
    let componentType = "counter";
    let componentName = "Counter";

    if (promptLower.includes("form")) {
      componentType = "form";
      componentName = "ContactForm";
    } else if (promptLower.includes("card")) {
      componentType = "card";
      componentName = "Card";
    }

    yield { type: "stream-start", warnings: [] };

    // Step 1: Create component file
    if (toolMessageCount === 1) {
      const text = `I'll create a ${componentName} component for you.`;
      yield { type: "text-start", id: "text-1" };
      for (const char of text) {
        yield { type: "text-delta", id: "text-1", delta: char };
        await this.delay(25);
      }
      yield { type: "text-end", id: "text-1" };

      const args = JSON.stringify({
        command: "create",
        path: `/components/${componentName}.jsx`,
        file_text: this.getComponentCode(componentType),
      });
      yield { type: "tool-input-start", id: "call_1", toolName: "str_replace_editor" };
      yield { type: "tool-input-delta", id: "call_1", delta: args };
      yield { type: "tool-input-end", id: "call_1" };
      yield { type: "tool-call", toolCallId: "call_1", toolName: "str_replace_editor", input: args };
      yield { type: "finish", finishReason: { unified: "tool-calls", raw: "tool_use" }, usage: { inputTokens: { total: 50 }, outputTokens: { total: 30 } } };
      return;
    }

    // Step 2: Enhance component
    if (toolMessageCount === 2) {
      const text = `Now let me enhance the component with better styling.`;
      yield { type: "text-start", id: "text-2" };
      for (const char of text) {
        yield { type: "text-delta", id: "text-2", delta: char };
        await this.delay(25);
      }
      yield { type: "text-end", id: "text-2" };

      const args = JSON.stringify({
        command: "str_replace",
        path: `/components/${componentName}.jsx`,
        old_str: this.getOldStringForReplace(componentType),
        new_str: this.getNewStringForReplace(componentType),
      });
      yield { type: "tool-input-start", id: "call_2", toolName: "str_replace_editor" };
      yield { type: "tool-input-delta", id: "call_2", delta: args };
      yield { type: "tool-input-end", id: "call_2" };
      yield { type: "tool-call", toolCallId: "call_2", toolName: "str_replace_editor", input: args };
      yield { type: "finish", finishReason: { unified: "tool-calls", raw: "tool_use" }, usage: { inputTokens: { total: 50 }, outputTokens: { total: 30 } } };
      return;
    }

    // Step 3: Create App.jsx
    if (toolMessageCount === 0) {
      const text = `This is a static response. You can place an Anthropic API key in the .env file to use the Anthropic API for component generation. Let me create an App.jsx file to display the component.`;
      yield { type: "text-start", id: "text-3" };
      for (const char of text) {
        yield { type: "text-delta", id: "text-3", delta: char };
        await this.delay(15);
      }
      yield { type: "text-end", id: "text-3" };

      const args = JSON.stringify({
        command: "create",
        path: "/App.jsx",
        file_text: this.getAppCode(componentName),
      });
      yield { type: "tool-input-start", id: "call_3", toolName: "str_replace_editor" };
      yield { type: "tool-input-delta", id: "call_3", delta: args };
      yield { type: "tool-input-end", id: "call_3" };
      yield { type: "tool-call", toolCallId: "call_3", toolName: "str_replace_editor", input: args };
      yield { type: "finish", finishReason: { unified: "tool-calls", raw: "tool_use" }, usage: { inputTokens: { total: 50 }, outputTokens: { total: 30 } } };
      return;
    }

    // Step 4: Final summary
    if (toolMessageCount >= 3) {
      const text = `Perfect! I've created:\n\n1. **${componentName}.jsx** - A fully-featured ${componentType} component\n2. **App.jsx** - The main app file that displays the component\n\nThe component is now ready to use. You can see the preview on the right side of the screen.`;

      yield { type: "text-start", id: "text-4" };
      for (const char of text) {
        yield { type: "text-delta", id: "text-4", delta: char };
        await this.delay(30);
      }
      yield { type: "text-end", id: "text-4" };
      yield { type: "finish", finishReason: { unified: "stop", raw: "stop_sequence" }, usage: { inputTokens: { total: 50 }, outputTokens: { total: 50 } } };
      return;
    }
  }

  private getComponentCode(componentType: string): string {
    switch (componentType) {
      case "form":
        return `import React, { useState } from 'react';

const ContactForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: ''
  });

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Form submitted:', formData);
  };

  return (
    <div className="max-w-md mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6">Contact Us</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input type="text" id="name" name="name" value={formData.name} onChange={handleChange} required
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input type="email" id="email" name="email" value={formData.email} onChange={handleChange} required
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">Message</label>
          <textarea id="message" name="message" value={formData.message} onChange={handleChange} required rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button type="submit" className="w-full bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 transition-colors">
          Send Message
        </button>
      </form>
    </div>
  );
};

export default ContactForm;`;

      case "card":
        return `import React from 'react';

const Card = ({ title = "Welcome to Our Service", description = "Discover amazing features.", imageUrl, actions }) => {
  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      {imageUrl && <img src={imageUrl} alt={title} className="w-full h-48 object-cover" />}
      <div className="p-6">
        <h3 className="text-xl font-semibold mb-2">{title}</h3>
        <p className="text-gray-600 mb-4">{description}</p>
        {actions && <div className="mt-4">{actions}</div>}
      </div>
    </div>
  );
};

export default Card;`;

      default:
        return `import { useState } from 'react';

const Counter = () => {
  const [count, setCount] = useState(0);

  return (
    <div className="flex flex-col items-center p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">Counter</h2>
      <div className="text-4xl font-bold mb-6">{count}</div>
      <div className="flex gap-4">
        <button onClick={() => setCount(count - 1)} className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors">Decrease</button>
        <button onClick={() => setCount(0)} className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors">Reset</button>
        <button onClick={() => setCount(count + 1)} className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">Increase</button>
      </div>
    </div>
  );
};

export default Counter;`;
    }
  }

  private getOldStringForReplace(componentType: string): string {
    switch (componentType) {
      case "form":
        return "    console.log('Form submitted:', formData);";
      case "card":
        return '      <div className="p-6">';
      default:
        return "  const increment = () => setCount(count + 1);";
    }
  }

  private getNewStringForReplace(componentType: string): string {
    switch (componentType) {
      case "form":
        return "    console.log('Form submitted:', formData);\n    alert('Thank you! We\\'ll get back to you soon.');";
      case "card":
        return '      <div className="p-6 hover:bg-gray-50 transition-colors">';
      default:
        return "  const increment = () => setCount(prev => prev + 1);";
    }
  }

  private getAppCode(componentName: string): string {
    if (componentName === "Card") {
      return `import Card from '@/components/Card';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <Card title="Amazing Product" description="This is a fantastic product!"
          actions={<button className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 transition-colors">Learn More</button>}
        />
      </div>
    </div>
  );
}`;
    }

    return `import ${componentName} from '@/components/${componentName}';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <${componentName} />
      </div>
    </div>
  );
}`;
  }

  async doGenerate(options: any): Promise<any> {
    const userPrompt = this.extractUserPrompt(options.prompt);
    const parts: V2StreamPart[] = [];
    for await (const part of this.generateMockStream(options.prompt, userPrompt)) {
      parts.push(part);
    }

    const textParts = parts.filter((p) => p.type === "text-delta").map((p) => (p as any).delta).join("");
    const finishPart = parts.find((p) => p.type === "finish") as any;

    return {
      content: textParts ? [{ type: "text", text: textParts }] : [],
      finishReason: finishPart?.finishReason || { unified: "stop", raw: "stop_sequence" },
      usage: { inputTokens: { total: 100 }, outputTokens: { total: 200 } },
      warnings: [],
      rawCall: { rawPrompt: options.prompt, rawSettings: {} },
    };
  }

  async doStream(options: any): Promise<any> {
    const userPrompt = this.extractUserPrompt(options.prompt);
    const self = this;

    const stream = new ReadableStream<V2StreamPart>({
      async start(controller) {
        try {
          for await (const chunk of self.generateMockStream(options.prompt, userPrompt)) {
            controller.enqueue(chunk);
          }
          controller.close();
        } catch (error) {
          controller.error(error);
        }
      },
    });

    return { stream, warnings: [], rawCall: { rawPrompt: options.prompt, rawSettings: {} } };
  }
}

export function getLanguageModel(): LanguageModel {
  const apiKey = process.env.ANTHROPIC_API_KEY;

  if (!apiKey || apiKey.trim() === "") {
    console.log("No ANTHROPIC_API_KEY found, using mock provider");
    return new MockLanguageModel("mock-claude-sonnet-4-0") as unknown as LanguageModel;
  }

  return anthropic(MODEL);
}
