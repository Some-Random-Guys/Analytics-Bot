class Profile:
    def __init__(self) -> None:
        # Discord IDs
        self.user_id: int = None
        self.guild_id: int = None

        # Message data
        self.messages = None
        self.top_words = []
        self.top_emojis = []

        # channel
        self.most_active_channel = None

        # mentions
        self.total_mentions = None

        self.most_mentioned = None
        self.no_of_times_most_mentioned = None

        self.most_mentioned_by = None
        self.no_of_times_most_mentioned_by = None

        # time
        self.most_active_hour = None
        self.most_active_day = None

