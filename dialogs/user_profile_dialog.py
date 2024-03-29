# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.dialogs import (
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
)
from botbuilder.dialogs.prompts import (
    TextPrompt,
    NumberPrompt,
    ChoicePrompt,
    ConfirmPrompt,
    AttachmentPrompt,
    PromptOptions,
    PromptValidatorContext,
)
from botbuilder.dialogs.choices import Choice
from botbuilder.core import MessageFactory, UserState

from data_models import UserProfile
import jieba

class UserProfileDialog(ComponentDialog):
    def __init__(self, user_state: UserState):
        super(UserProfileDialog, self).__init__(UserProfileDialog.__name__)

        self.user_profile_accessor = user_state.create_property("UserProfile")

        self.add_dialog(
            WaterfallDialog(
                WaterfallDialog.__name__,
                [
                    self.podcast_step,
                    self.name_step,
                    self.name_confirm_step,
                    self.query_step,
                    self.summary_step,
                ],
            )
        )
        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(ChoicePrompt(ChoicePrompt.__name__))
        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))
        
        self.initial_dialog_id = WaterfallDialog.__name__

    async def podcast_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        # WaterfallStep always finishes with the end of the Waterfall or with another dialog;
        # here it is a Prompt Dialog. Running a prompt here means the next WaterfallStep will
        # be run when the users response is received.
        return await step_context.prompt(
            ChoicePrompt.__name__,
            PromptOptions(
                prompt=MessageFactory.text("Please select the podcast you are interested in."),
                choices=[Choice("好味小姐"), Choice("股癌"), Choice("百靈果")],
            ),
        )

    async def name_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["podcast"] = step_context.result.value

        return await step_context.prompt(
            TextPrompt.__name__,
            PromptOptions(prompt=MessageFactory.text("Please enter your name.")),
        )

    async def name_confirm_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        step_context.values["name"] = step_context.result

        # We can send messages to the user at any point in the WaterfallStep.
        await step_context.context.send_activity(
            MessageFactory.text(f"Thanks {step_context.result}")
        )

        # WaterfallStep always finishes with the end of the Waterfall or
        # with another dialog; here it is a Prompt Dialog.
        return await step_context.prompt(
            ConfirmPrompt.__name__,
            PromptOptions(
                prompt=MessageFactory.text("Would you like to give your query?")
            ),
        )

    async def query_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        if step_context.result:
            # User said "yes" so we will be prompting for the query.
            # WaterfallStep always finishes with the end of the Waterfall or with another dialog,
            # here it is a Prompt Dialog.
            return await step_context.prompt(
                TextPrompt.__name__,
                PromptOptions(
                    prompt=MessageFactory.text("Please enter your query.")),
            )

        # User said "no" so we will skip the next step. Give -1 as the query.
        return await step_context.next(-1)


    # async def confirm_step(
    #     self, step_context: WaterfallStepContext
    # ) -> DialogTurnResult:
    #     step_context.values["picture"] = (
    #         None if not step_context.result else step_context.result[0]
    #     )

    #     # WaterfallStep always finishes with the end of the Waterfall or
    #     # with another dialog; here it is a Prompt Dialog.
    #     return await step_context.prompt(
    #         ConfirmPrompt.__name__,
    #         PromptOptions(prompt=MessageFactory.text("Is this ok?")),
    #     )

    async def summary_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        step_context.values["query"] = step_context.result
        if step_context.result:
            # Get the current profile object from user state.  Changes to it
            # will saved during Bot.on_turn.
            user_profile = await self.user_profile_accessor.get(
                step_context.context, UserProfile
            )

            user_profile.podcast = step_context.values["podcast"]
            user_profile.name = step_context.values["name"]
            user_profile.query = step_context.values["query"]
            #user_profile.picture = step_context.values["picture"]

            msg = f"Choice of podcast : {user_profile.podcast} \nYour name : {user_profile.name}"
            if user_profile.query != -1:
                msg += f"\nQuery : {user_profile.query}"
                seg_list = jieba.lcut(user_profile.query)
                seg_list_total = jieba.lcut(user_profile.query, cut_all=True)
                seg_list_search = jieba.lcut_for_search(user_profile.query)
                msg += f"\nJieba精確模式 : {seg_list}"
                msg += f"\nJieba全模式 : {seg_list_total}"
                msg += f"\nJieba搜索引擎模式 : {seg_list_search}\n"

            await step_context.context.send_activity(MessageFactory.text(msg))

            # if user_profile.picture:
            #     await step_context.context.send_activity(
            #         MessageFactory.attachment(
            #             user_profile.picture, "This is your profile picture."
            #         )
            #     )
            # else:
            #     await step_context.context.send_activity(
            #         "A profile picture was saved but could not be displayed here."
            #     )
        else:
            await step_context.context.send_activity(
                MessageFactory.text("Thanks. Not providing query.")
            )

        # WaterfallStep always finishes with the end of the Waterfall or with another
        # dialog, here it is the end.
        return await step_context.end_dialog()
