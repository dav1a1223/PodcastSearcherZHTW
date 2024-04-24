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
from .text_processor import TextProcessor

class UserProfileDialog(ComponentDialog):
    def __init__(self, user_state: UserState):
        super(UserProfileDialog, self).__init__(UserProfileDialog.__name__)

        self.user_profile_accessor = user_state.create_property("UserProfile")

        self.add_dialog(
            WaterfallDialog(
                WaterfallDialog.__name__,
                [
                    self.podcast_step,
                    self.query_step,
                    self.confirm_step,
                    self.summary_step,
                    self.handle_query_again,
                    self.final_step
                ],
            )
        )
        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(ChoicePrompt(ChoicePrompt.__name__))
        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))
        
        self.initial_dialog_id = WaterfallDialog.__name__

    async def podcast_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        return await step_context.prompt(
            ChoicePrompt.__name__,
            PromptOptions(
                prompt=MessageFactory.text("Please select the podcast you are interested in."),
                choices=[Choice("podcast A"), Choice("podcast B"), Choice("podcast C")],
            ),
        )

    async def query_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        podcast = step_context.result.value
        step_context.values["podcast"] = podcast

        await step_context.context.send_activity(
            MessageFactory.text(f"Your choice is {podcast}.")
        )

        return await step_context.prompt(
                TextPrompt.__name__,
                PromptOptions(
                    prompt=MessageFactory.text("Please enter your query.\nUse，to separate each term.")),
        )
    
    async def confirm_step( self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["query"] = step_context.result
        
        user_profile = await self.user_profile_accessor.get(
                step_context.context, UserProfile
        )    
        user_profile.podcast = step_context.values["podcast"]
        user_profile.query = step_context.values["query"]

        processor = TextProcessor()
        seg_list =  processor.word_segmentation(user_profile.query, True)
        msg = f"Choice of podcast : {user_profile.podcast} \nYour query : {seg_list}"

        await step_context.context.send_activity(MessageFactory.text(msg))

        return await step_context.prompt(
            ConfirmPrompt.__name__,
            PromptOptions(prompt=MessageFactory.text("Are you satisfied with the search result?")),
        )
    
    async def summary_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["satisfied"] = step_context.result
        if step_context.values["satisfied"]:
            return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("Do you want to search for another podcast program?")),
            )
        else:
            return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("Do you want to enter your query again?")),
            )
    async def handle_query_again(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        if not step_context.values["satisfied"]:
            query_another = step_context.result
            if query_another: #modify -> 回到query_step
                return await step_context.replace_dialog(self.initial_dialog_id)
            else:         
                return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("Do you want to search for another podcast program?")),
                )
        else:
            step_context.values["search_another"] = step_context.result
            return await step_context.continue_dialog()

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        if step_context.values["satisfied"]:
            search_another = step_context.values["search_another"]
        else: 
            search_another = step_context.result
            
        if search_another:
            return await step_context.replace_dialog(self.initial_dialog_id)
        else:
            await step_context.context.send_activity(MessageFactory.text('Thank you~'))
            return await step_context.end_dialog()
