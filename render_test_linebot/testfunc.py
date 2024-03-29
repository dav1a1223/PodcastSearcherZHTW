from linebot import LineBotApi,WebhookParser
from linebot.models import *
from settings import *

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

def quicktest(event):
    try:
        t=TextSendMessage(
            text='quick reply 按鈕測試',
            quick_reply=QuickReply(
                items=[
                    QuickReplyButton(
                        action=MessageAction(
                            label='message',
                            data='action=quick & item=1',
                            text='MessageAction'
                        )
                    ),
                    QuickReplyButton(
                        action=URIAction(
                            label='open URL',
                            uri="https://www.google.com.tw/"
                        )
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, t)  
    except Exception as e:
        print(f"Error in quicktest: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='失敗'))

def buttontest(event):
    try:
        t=TemplateSendMessage(
            alt_text='Buttons template',
                template=ButtonsTemplate(
                    title='Button 按鈕測試',
                    text='請選擇功能',
                    actions=[
                        PostbackAction(
                            label='功能1',
                            text='text1'
                        ),
                        MessageTemplateAction(
                            label='功能2',
                            text='text2'
                        )
                    ]
                )
        )
        line_bot_api.reply_message(event.reply_token,t)
    except Exception as e:
        print(f"Error in quicktest: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='失敗')) 

def carouseltest(event):
    try:
        t=TemplateSendMessage(
            alt_text='Carousel template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://images.pexels.com/photos/6686455/pexels-photo-6686455.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
                        title='分類:投資',
                        text='選擇你有興趣的 podcast',
                        actions=[
                            PostbackAction(
                                label='股癌',
                                data='action=test_1'
                            ),
                            PostbackAction(
                                label='M觀點',
                                data='action=test_2'
                            ),
                            PostbackAction(
                                label='財報狗',
                                data='action=test_3'
                            )
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://images.pexels.com/photos/6686455/pexels-photo-6686455.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
                        title='分類:喜劇',
                        text='選擇你有興趣的 podcast',
                        actions=[
                            PostbackAction(
                                label='百靈果',
                                data='action=test_4'
                            ),
                            PostbackAction(
                                label='好味小姐',
                                data='action=test_5'
                            ),
                            PostbackAction(
                                label='面白',
                                data='action=test_6'
                            ),
                        ]
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token,t)
    except Exception as e:
        print(f"Error in quicktest: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='失敗')) 
