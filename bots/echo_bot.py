# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.schema import ChannelAccount
from linebot.models import TemplateSendMessage, ButtonsTemplate, PostbackTemplateAction

class EchoBot(ActivityHandler):
    async def on_members_added_activity(
        self, members_added: [ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")

    async def on_message_activity(self, turn_context: TurnContext):
        if turn_context.activity.text=="@button":

            buttons_template = ButtonsTemplate(
                #thumbnail_image_url='https://example.com/image.jpg',
                title='My Button Template',
                text='Please select an option:',
                actions=[
                    PostbackTemplateAction(
                        label='Option 1',
                        data='action=option1'
                    ),
                    PostbackTemplateAction(
                        label='Option 2',
                        data='action=option2'
                    )
                ]
            )

            # Create a template message containing the button template
            template_message = TemplateSendMessage(
                alt_text='Button Template',
                template=buttons_template
            )

            # Send the template message
            return await turn_context.send_activity(template_message)
        else:   
            return await turn_context.send_activity(
                MessageFactory.text(f"Echo: {turn_context.activity.text}")
            )
