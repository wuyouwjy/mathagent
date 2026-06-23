// ============================================================
// components/LatexRenderer.tsx — LaTeX 数学公式渲染 & Markdown 展示
// ============================================================
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface LatexRendererProps {
  content: string;
}

const LatexRenderer: React.FC<LatexRendererProps> = ({ content }) => {
  if (!content) return <span>-</span>;

  // 检测是否包含 LaTeX 或 Markdown 标记
  const hasLatex = /\$\$|\$|\\begin\{|\\frac|\\int|\\sum|\\lim/.test(content);
  const hasMarkdown = /[#*>`\-\[\]|!]/.test(content);

  if (!hasLatex && !hasMarkdown) {
    return <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>;
  }

  return (
    <div style={{ lineHeight: 1.8 }}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const inline = !match;
            return !inline ? (
              <SyntaxHighlighter
                style={oneDark}
                language={match![1]}
                PreTag="div"
                customStyle={{ borderRadius: 8, margin: '8px 0' }}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className={className} {...props} style={{ color: '#f59e0b' }}>
                {children}
              </code>
            );
          },
          // Inline math: $...$
          span({ children, ...props }: { children?: React.ReactNode; [key: string]: unknown } & React.HTMLAttributes<HTMLSpanElement>) {
            const text = String(children || '');
            if (text.startsWith('$') && text.endsWith('$')) {
              return <span className="katex-inline" {...props}>{children}</span>;
            }
            return <span {...props}>{children}</span>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default LatexRenderer;
