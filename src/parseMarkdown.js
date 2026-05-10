/**
 * Markdown-to-HTML converter with XSS prevention.
 *
 * S-9: the previous hand-rolled parser interpolated href without escaping
 * quotes, letting payloads like
 *   [x](https://a.com" onerror="alert(1))
 * break out of the attribute. We now route everything through `marked` for
 * parsing and `DOMPurify` for sanitization — neither library has the
 * attribute-injection class of bug.
 */

import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Force every outgoing <a> to open in a new tab with safe rel.
// One-time hook install; guarded so repeated imports don't double-register.
if (typeof window !== 'undefined' && !window.__AME_DOMPURIFY_HOOK__) {
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noopener noreferrer')
    }
  })
  window.__AME_DOMPURIFY_HOOK__ = true
}

const ALLOWED_TAGS = [
  'a', 'br', 'code', 'em', 'strong',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'blockquote', 'p', 'pre',
  'ul', 'ol', 'li', 'img',
]

const ALLOWED_ATTR = ['href', 'target', 'rel', 'src', 'alt', 'class']

// Matches marked's recommended safe-URI regex: http/https/mailto, plus
// relative URIs that do not look like javascript: / data: / vbscript:.
const ALLOWED_URI_REGEXP = /^(?:(?:https?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i

export default function parseMarkdown(text) {
  if (!text) return ''

  let html
  try {
    html = marked.parse(String(text), { breaks: true, gfm: true })
  } catch {
    // If marked fails for any reason, fall back to the literal text escaped.
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP,
  })

  return clean
}
