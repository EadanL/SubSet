from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


class ReadableConsoleEmailBackend(ConsoleEmailBackend):
    """Development backend that prints the plain message text.

    Django's console backend prints the raw encoded email. Long lines (such as a
    password-reset link with a UUID in it) get quoted-printable soft line breaks,
    so a link copied from the console arrives broken. Printing the decoded body
    keeps every link whole on one line.
    """

    def write_message(self, message):
        self.stream.write(f"From: {message.from_email}\n")
        self.stream.write(f"To: {', '.join(message.to)}\n")
        self.stream.write(f"Subject: {message.subject}\n\n")
        self.stream.write(f"{message.body}\n")
        self.stream.write("-" * 79)
        self.stream.write("\n")
