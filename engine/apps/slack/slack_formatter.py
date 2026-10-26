import re

import emoji
import markdown2


class SlackFormatter:
    _MENTION_PAT = re.compile(r"<((?:#C|@[UB])\w+)(?:\|([A-Za-z0-9.-_]+))?>")
    _HASHTAG_PAT = re.compile(r"(^| )#[A-Za-z][\w.\-_]+( |$)")
    _LINK_PAT = re.compile(r"<(https|http|mailto):[A-Za-z0-9_\.\-\/\?\,\=\#\:\@\& ]+\|[^>]+>")

    def __init__(self, organization):
        self.__ORGANIZATION = organization
        self.channel_mention_format = "#{}"
        self.user_mention_format = "@{}"
        self.hyperlink_mention_format = '<a href="{url}">{title}</a>'

    def format(self, message):
        """
        Overriden original render_text method.
        Now it is responsible only for formatting slack mentions, channel names, etc.
        """
        if message is None:
            return
        message = message.replace("<!channel>", "@channel")
        message = message.replace("<!channel|@channel>", "@channel")
        message = message.replace("<!here>", "@here")
        message = message.replace("<!here|@here>", "@here")
        message = message.replace("<!everyone>", "@everyone")
        message = message.replace("<!everyone|@everyone>", "@everyone")
        message = self.slack_to_accepted_emoji(message)

        # Handle mentions of users, channels and bots (e.g "<@U0BM1CGQY|calvinchanubc> has joined the channel")
        message = self._MENTION_PAT.sub(self._sub_annotated_mention, message)
        # Handle links
        message = self._LINK_PAT.sub(self._sub_hyperlink, message)
        # Introduce unicode emoji
        message = emoji.emojize(message, language="alias")

        return message

    def render_text(self, message, process_markdown=True):
        message = self.format(message)
        message = self._HASHTAG_PAT.sub(self._sub_hashtag, message)
        if process_markdown:
            message = markdown2.markdown(
                message.replace("*", "**"),
                extras=["cuddled-lists", "fenced-code-blocks", "pyshell"],
            ).strip()
        return message.replace("\n\n<ul>", "<ul>").replace("\n<li>", "<li>")

    def _sub_hashtag(self, matchobj):
        text = matchobj.group(0)
        return "{}<b>{}</b>{}".format(
            " " if text.startswith(" ") else "", text.strip(), " " if text.endswith(" ") else ""
        )

    def slack_to_accepted_emoji(self, message):
        """Overridden original method to fix regex that replaces dashes in links"""
        message = re.sub(
            r":([a-zA-Z0-9<>/:])([^ <>/:]+):",  # overridden regex
            lambda x: ":{}{}:".format(x.group(1), x.group(2).replace("-", "_")),
            message,
        )

        # https://github.com/Ranks/emojione/issues/114
        message = message.replace(":simple_smile:", ":slightly_smiling_face:")
        return message

    def _sub_hyperlink(self, matchobj):
        compound = matchobj.group(0)[1:-1]
        if len(compound.split("|")) == 2:
            url, title = compound.split("|")
        else:
            url, title = compound, compound
        result = self.hyperlink_mention_format.format(url=url, title=title)
        return result

    def _sub_annotated_mention(self, matchobj):
        """
        Overrided method to use db search instead of self.__USER_DATA and self.__CHANNEL_DATA (see original method)
        to search channels and users by their slack_ids
        """
        # Matchobj have format <channel_id/channel_name> or <user_id/user_name>
        ref_id = matchobj.group(1)[1:]  # drop #/@ from the start, we don't care.
        annotation = matchobj.group(2)
        # check if mention channel
        if ref_id.startswith("C"):
            mention_format = self.channel_mention_format
            # channel could be mentioned only with its slack_id <channel_id>
            if not annotation:
                # search channel_name by slack_id in cache
                annotation = self._sub_annotated_mention_slack_channel(ref_id)
        else:  # Same for user
            mention_format = self.user_mention_format
            if not annotation:
                annotation = self._sub_annotated_mention_slack_user(ref_id)
        return mention_format.format(annotation)

    def _sub_annotated_mention_slack_channel(self, ref_id):
        channel = None
        slack_team_identity = self.__ORGANIZATION.slack_team_identity
        if slack_team_identity is not None:
            cached_channels = slack_team_identity.get_cached_channels(slack_id=ref_id)
            if len(cached_channels) > 0:
                channel = cached_channels[0].name
            annotation = channel if channel else ref_id
        else:
            annotation = ref_id
        return annotation

    def _sub_annotated_mention_slack_user(self, ref_id):
        from apps.slack.models import SlackUserIdentity

        slack_user_identity = SlackUserIdentity.objects.filter(
            slack_team_identity=self.__ORGANIZATION.slack_team_identity, slack_id=ref_id
        ).first()

        annotation = ref_id
        if slack_user_identity is not None:
            if slack_user_identity.profile_display_name:
                annotation = slack_user_identity.profile_display_name
            elif slack_user_identity.slack_verbal:
                annotation = slack_user_identity.slack_verbal
        return annotation
