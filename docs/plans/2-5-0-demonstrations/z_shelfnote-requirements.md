# Shelfnote: find a book by its title or author

## Problem

With more than a few books on the shelf, finding one means reading the whole list.

## The change

### The API

`GET /books?q=<text>` answers the books whose title or author contains `<text>`, ignoring case.

- It answers the same book objects, in the same order, as `GET /books` does.
- Without `q`, or with an empty `q`, `GET /books` answers every book, as it does today.
- A `q` that matches nothing answers an empty list, with status 200.

### The page

A search page at `/search`.

- Its view's root element carries `data-testid="search-view"`.
- It has a text input (`type="text"`) labelled `Search`, and a button named `Search`.
- Pressing the button shows each matching book's title and author, and each result links to its
  book's page (`/books/:id`).
- When nothing matches, the page says so, and shows no book.

## Constraints

- As `CONTRIBUTING.md` asks: a test for each status code the API change can answer, the frontend
  tests passing, and each new endpoint handler under thirty lines.
- Every existing endpoint and page behaves as it does today.

## Out of scope

Editing or deleting books, and any change to the other pages.
