import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  children?: string;
  /** Alias for `children` — inbox and other call sites may pass `text` */
  text?: string;
};

export default function ChatMarkdown({ children, text }: Props) {
  const content = text ?? children ?? "";
  return (
    <div className="chat-gpt-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: c }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {c}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
