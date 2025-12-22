import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Document RAG Engine",
  description: "Ask questions about your enterprise documents using semantic search and LLM analysis",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
