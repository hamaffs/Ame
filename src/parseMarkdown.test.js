import { describe, it, expect } from 'vitest'
import parseMarkdown from './parseMarkdown.js'

describe('parseMarkdown', () => {
  // --- Basic rendering ---------------------------------------------------

  it('returns empty string for falsy input', () => {
    expect(parseMarkdown('')).toBe('')
    expect(parseMarkdown(null)).toBe('')
    expect(parseMarkdown(undefined)).toBe('')
  })

  it('renders plain text wrapped in <p>', () => {
    const result = parseMarkdown('hello')
    expect(result).toContain('<p>hello</p>')
  })

  it('renders bold text', () => {
    const result = parseMarkdown('**bold**')
    expect(result).toContain('<strong>bold</strong>')
  })

  it('renders italic text', () => {
    const result = parseMarkdown('*italic*')
    expect(result).toContain('<em>italic</em>')
  })

  it('renders inline code', () => {
    const result = parseMarkdown('use `console.log`')
    expect(result).toContain('<code>console.log</code>')
  })

  it('renders fenced code blocks', () => {
    const result = parseMarkdown('```js\nconsole.log("hi")\n```')
    expect(result).toContain('<pre>')
    expect(result).toContain('<code')
    expect(result).toContain('console.log')
  })

  // --- Link rendering ----------------------------------------------------

  it('renders http links', () => {
    const result = parseMarkdown('[Google](https://google.com)')
    expect(result).toContain('href="https://google.com"')
    expect(result).toContain('target="_blank"')
    expect(result).toContain('rel="noopener noreferrer"')
  })

  it('renders mailto links', () => {
    const result = parseMarkdown('[Email](mailto:test@example.com)')
    expect(result).toContain('href="mailto:test@example.com"')
  })

  // --- XSS Prevention (Bug 17) ------------------------------------------

  it('blocks javascript: URI scheme', () => {
    const result = parseMarkdown('[click me](javascript:alert(1))')
    expect(result.toLowerCase()).not.toContain('href="javascript')
    expect(result).toContain('click me')
  })

  it('blocks javascript: with mixed case', () => {
    const result = parseMarkdown('[xss](JaVaScRiPt:alert(document.cookie))')
    expect(result.toLowerCase()).not.toContain('href="javascript')
  })

  it('blocks data: URI scheme', () => {
    const result = parseMarkdown('[xss](data:text/html,<script>alert(1)</script>)')
    expect(result.toLowerCase()).not.toContain('href="data:')
    expect(result).not.toContain('<script>')
  })

  it('blocks vbscript: URI scheme', () => {
    const result = parseMarkdown('[xss](vbscript:MsgBox("pwned"))')
    expect(result.toLowerCase()).not.toContain('href="vbscript')
  })

  it('blocks file: URI scheme', () => {
    const result = parseMarkdown('[secret](file:///etc/passwd)')
    expect(result.toLowerCase()).not.toContain('href="file:')
  })

  // --- S-9: attribute-injection payloads --------------------------------

  it('does not let href break out of the attribute (S-9 regression)', () => {
    const payload = '[x](https://a.com" onerror="alert(1))'
    const result = parseMarkdown(payload)
    // onerror must NOT appear as a real attribute inside any tag.
    // It can survive as inert text inside a <p>, which is harmless.
    expect(result).not.toMatch(/<[^>]*onerror\s*=/i)
    // And no extra href injected.
    const hrefMatches = (result.match(/href=/g) || []).length
    expect(hrefMatches).toBeLessThanOrEqual(1)
    // The text content, if extracted, should not produce a JS execution node.
    const div = document.createElement('div')
    div.innerHTML = result
    const hasOnErrorAttr = Array.from(div.querySelectorAll('*')).some(
      (el) => el.hasAttribute('onerror'),
    )
    expect(hasOnErrorAttr).toBe(false)
  })

  it('drops on* event handlers even if authored HTML sneaks in', () => {
    const result = parseMarkdown('<a href="x" onclick="alert(1)">go</a>')
    expect(result).not.toContain('onclick')
  })

  it('strips <script> tags entirely', () => {
    const result = parseMarkdown('<script>alert(1)</script>')
    expect(result).not.toContain('<script>')
  })

  // --- List rendering ----------------------------------------------------

  it('renders unordered list items', () => {
    const result = parseMarkdown('- item one\n- item two')
    expect(result).toContain('<li>item one</li>')
    expect(result).toContain('<li>item two</li>')
    expect(result).toContain('<ul>')
  })

  it('renders ordered list items', () => {
    const result = parseMarkdown('1. first\n2. second')
    expect(result).toContain('<li>first</li>')
    expect(result).toContain('<li>second</li>')
  })
})
