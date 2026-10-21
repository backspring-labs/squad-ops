# Shelfnote — product requirements (v0.1)

## 1. Summary

Shelfnote is a shared reading list for a small group (a book club, a team, a household). Anyone in
the group adds a book they want to read, and anyone can leave a short note on it: why it's worth
reading, a quote, a reaction after finishing it.

## 2. Users

One shared list, no accounts. A person types their name when they add a book or leave a note.

## 3. Core scope

### 3.1 The list
- Shows every book on the list, newest first: its title, its author, who added it and how many
  notes it has.
- An empty list says so, and offers to add the first book.

### 3.2 Adding a book
- A form with the title (required), the author (required) and who is adding it (required).
- A missing required field is refused with a clear message, and nothing is added.

### 3.3 A book's page
- Shows the book's title, author and who added it, then its notes, oldest first, each with who
  wrote it.
- A form to leave a note: who is writing (required) and the note (required, at most 500
  characters).
- A book that doesn't exist shows a not-found message.

## 4. Errors

Every error the API returns has a code and a message the page can show as it is.

## 5. Out of scope for now

Accounts, editing or deleting books and notes, ratings, search, and persistence beyond the running
process.
