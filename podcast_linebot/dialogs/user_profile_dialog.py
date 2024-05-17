# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.dialogs import (
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    DialogTurnStatus
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
from botbuilder.core import MessageFactory, UserState, CardFactory
from botbuilder.schema import (HeroCard, Attachment, CardImage, CardAction, ActionTypes, AttachmentLayoutTypes)
import os
import json
connection_string = os.environ.get("COSMOS_DB_CONNECTION_STRING","")

from data_models import UserProfile
from .text_processor import TextProcessor
from .query_db import CosmosDBQuery

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
                    # self.handle_query_again,
                    self.final_step
                ],
            )
        )
        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(ChoicePrompt(ChoicePrompt.__name__))
        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))
        
        self.initial_dialog_id = WaterfallDialog.__name__

    async def podcast_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        if step_context.context.activity.text== "@search" or "Yes":
            return await step_context.prompt(
                ChoicePrompt.__name__,
                PromptOptions(
                    prompt=MessageFactory.text("請選擇你有興趣查詢的Podcast節目～"),
                    choices=[Choice("好味小姐")],
                )
            )
        else:
            return DialogTurnResult(DialogTurnStatus.Complete)
    
    async def query_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        podcast = step_context.result.value
        step_context.values["podcast"] = podcast

        await step_context.context.send_activity(
            MessageFactory.text(f"你的選擇是：{podcast}")
        )

        return await step_context.prompt(
                TextPrompt.__name__,
                PromptOptions(
                    prompt=MessageFactory.text("請輸入你想搜尋的內容，若是輸入關鍵字，請用「，」分隔。")),
        )
    
    async def confirm_step( self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["query"] = step_context.result
        
        user_profile = await self.user_profile_accessor.get(
                step_context.context, UserProfile
        )    
        user_profile.podcast = step_context.values["podcast"]
        user_profile.query = step_context.values["query"]

        processor = TextProcessor()
        user_query = processor.word_segmentation(user_profile.query, True) # 斷詞後的 query list 型態
        str_query = ' '.join(user_query) # 轉成 string 格式
        db_query = CosmosDBQuery(connection_string, 'Score','stopwords.txt')
        resulting_terms = db_query.process_query(str_query) # return 搜尋結果
        # formatted_output = ""
        
        reply = MessageFactory.list([])
        reply.attachment_layout = AttachmentLayoutTypes.carousel
        for idx, doc in enumerate(resulting_terms['documents'], start=1):
            doc_id = doc['document_id']
            terms = ', '.join([f'"{term}": {term_data["freq"]}' for term, term_data in doc['terms'].items()])
            url = doc['url']
            # formatted_output += f"{idx}. {doc_id}\n{terms}\n"

            card = HeroCard(
                title = doc_id,
                # images=[
                #     CardImage(
                #         url="https://images.pexels.com/photos/6686442/pexels-photo-6686442.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2"
                #     )
                # ],
                text = "以下為搜尋關鍵字在該集出現的次數:\n\n" + terms,
                buttons=[
                    CardAction(
                        type=ActionTypes.open_url,
                        title="Open URL",
                        value=url,
                    )
                ],
            )
            reply.attachments.append(CardFactory.hero_card(card))

        await step_context.context.send_activity(reply)
        

        return await step_context.prompt(
            ConfirmPrompt.__name__,
            PromptOptions(prompt=MessageFactory.text("是否滿意此搜尋結果？")),
        )
    
    async def summary_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["satisfied"] = step_context.result
        if step_context.values["satisfied"]:
            await step_context.context.send_activity(MessageFactory.text('搜尋結束，謝謝您~'))
            return await step_context.end_dialog()
        else:
            text = "是否要再重新搜尋呢？" + "\n" + "（💡提示：輸入越多出現次數高的關鍵字，搜尋結果會更準確唷！）"
            return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text(text)),
            )
        
    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["search_again"] = step_context.result
        if step_context.values["search_again"]:
            return await step_context.replace_dialog(self.initial_dialog_id)
        else:
            await step_context.context.send_activity(MessageFactory.text('搜尋結束，謝謝您的使用～歡迎填寫回饋問卷，分享您的想法和建議，這對我們來說非常重要，感謝您！https://forms.gle/e4aWqA5WjBQyXLNk8'))
            return await step_context.end_dialog()

    '''async def summary_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        step_context.values["satisfied"] = step_context.result
        if step_context.values["satisfied"]:
            return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("你想搜尋其他的Podcast節目嗎？")),
            )
        else:
            return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("是否要再重新輸入搜尋內容呢？")),
            )
    async def handle_query_again(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        if not step_context.values["satisfied"]:
            query_another = step_context.result
            if query_another: #modify -> 回到query_step
                # step_context.context.active_dialog.state["stepIndex"] = step_context.context.active_dialog.state["stepIndex"] - 3
                # return await self.query_step(step_context)
                return await step_context.replace_dialog(self.initial_dialog_id)
            else:         
                return await step_context.prompt(
                ConfirmPrompt.__name__,
                PromptOptions(prompt=MessageFactory.text("你想搜尋其他的Podcast節目嗎？")),
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
            await step_context.context.send_activity(MessageFactory.text('搜尋結束，謝謝您~'))
            return await step_context.end_dialog()'''
