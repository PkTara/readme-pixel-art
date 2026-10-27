class User:
    def __init__(self, login):
        self.login = login


class Issue:
    """Stands in for a PyGithub Issue and records everything the bot does to it"""

    def __init__(self, title='', body='', author='@player1'):
        self.title = title
        self.body = body
        self.user = User(author.lstrip('@'))
        self.comments = []
        self.labels = []
        self.state = 'open'

    def create_comment(self, text):
        self.comments.append(text)

    def edit(self, state=None, labels=None, **kwargs):
        if state is not None:
            self.state = state
        if labels is not None:
            self.labels = list(labels)

    def add_to_labels(self, *labels):
        self.labels += list(labels)
