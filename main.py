import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes, CallbackContext
from dotenv import load_dotenv
import time
from datetime import datetime

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv("ADMIN_IDS", "").split(",") if admin_id]
REQUESTS_CHANNEL_ID = os.getenv("REQUESTS_CHANNEL_ID")
REQUIRED_CHANNEL_ID = os.getenv("REQUIRED_CHANNEL_ID")
REQUIRED_CHANNEL_USERNAME = os.getenv("REQUIRED_CHANNEL_USERNAME", "").replace("@", "")

# Dictionary to store pending requests
# Format: {request_id: {'user_id': user_id, 'message_id': message_id, 'status': 'pending', 'timestamp': timestamp}}
pending_requests = {}

# Dict to track user membership status
user_membership_status = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Check if user is a member of the required channel
    if not await check_user_membership(user_id, context):
        await send_join_requirement(update, context)
        return
    
    # Create keyboard with request channel button
    keyboard = [
        [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Welcome to File Finder Bot! Send me a screenshot or image of the video/file you're looking for, "
        "and I'll forward it to our admins. Once they find it, you'll be notified!",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user_id = update.effective_user.id
    
    # Check if user is a member of the required channel
    if not await check_user_membership(user_id, context):
        await send_join_requirement(update, context)
        return
    
    # Create keyboard with request channel button
    keyboard = [
        [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📖 How to use File Finder Bot:\n\n"
        "1. Send a clear screenshot/image of the video or file you're looking for\n"
        "2. Your request will be forwarded to our admin team\n"
        "3. Wait for notification when your file is ready\n"
        "4. Check our Requested Videos Channel for all approved content\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Check status of your pending requests\n"
        "/verify - Verify your channel membership",
        reply_markup=reply_markup
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check status of user's pending requests."""
    user_id = update.effective_user.id
    
    # Check if user is a member of the required channel
    if not await check_user_membership(user_id, context):
        await send_join_requirement(update, context)
        return
    
    user_requests = {req_id: req for req_id, req in pending_requests.items() if req['user_id'] == user_id}
    
    if not user_requests:
        await update.message.reply_text("You don't have any pending requests.")
        return
    
    status_message = "Your pending requests:\n\n"
    for req_id, req in user_requests.items():
        timestamp = datetime.fromtimestamp(req['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        status_message += f"Request ID: {req_id}\nStatus: {req['status']}\nSubmitted: {timestamp}\n\n"
    
    # Create keyboard with request channel button
    keyboard = [
        [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(status_message, reply_markup=reply_markup)

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually verify channel membership."""
    user_id = update.effective_user.id
    
    if await check_user_membership(user_id, context, force_check=True):
        # Create keyboard with request channel button
        keyboard = [
            [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ Your membership has been verified! You can now use the bot.",
            reply_markup=reply_markup
        )
    else:
        await send_join_requirement(update, context)

async def check_user_membership(user_id, context, force_check=False):
    """Check if user is a member of the required channel."""
    # If we've checked recently and not forcing a check, return cached result
    current_time = time.time()
    if not force_check and user_id in user_membership_status:
        last_check, is_member = user_membership_status[user_id]
        # Cache membership status for 1 hour
        if current_time - last_check < 3600:
            return is_member
    
    try:
        chat_member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        is_member = chat_member.status in ['member', 'administrator', 'creator']
        
        # Update cache
        user_membership_status[user_id] = (current_time, is_member)
        return is_member
    except Exception as e:
        logger.error(f"Error checking membership for user {user_id}: {e}")
        # Assume not a member on error
        user_membership_status[user_id] = (current_time, False)
        return False

async def send_join_requirement(update, context):
    """Send message asking user to join required channel."""
    join_button = InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")
    verify_button = InlineKeyboardButton("🔄 Verify Membership", callback_data="verify_membership")
    keyboard = [[join_button], [verify_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ You need to join our channel to use this bot!\n\n"
        f"Please join @{REQUIRED_CHANNEL_USERNAME} and then click 'Verify Membership' button.",
        reply_markup=reply_markup
    )

async def track_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track chat member updates."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    
    was_member, is_member = result
    user_id = update.effective_user.id
    
    # Update membership status in cache
    user_membership_status[user_id] = (time.time(), is_member)

def extract_status_change(chat_member_update: ChatMemberUpdated):
    """Extract status change from ChatMemberUpdated event."""
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))
    
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    
    was_member = old_status in ["member", "administrator", "creator"]
    is_member = new_status in ["member", "administrator", "creator"]
    
    return was_member, is_member

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user sending photo for file request."""
    user_id = update.effective_user.id
    
    # Check if user is a member of the required channel
    if not await check_user_membership(user_id, context):
        await send_join_requirement(update, context)
        return
    
    user = update.effective_user
    photo = update.message.photo[-1]  # Get the largest photo
    
    # Generate a unique request ID
    request_id = int(time.time())
    
    # Store request in pending_requests
    pending_requests[request_id] = {
        'user_id': user_id,
        'message_id': update.message.message_id,
        'status': 'pending',
        'timestamp': time.time()
    }
    
    # Create keyboard for admin actions
    keyboard = [
        [
            InlineKeyboardButton("Approve", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Forward request to admin channel
    caption = (
        f"New file request from {user.mention_html()}\n"
        f"User ID: {user_id}\n"
        f"Request ID: {request_id}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await context.bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=photo.file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    # Confirm to user
    keyboard = [
        [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Your request has been submitted! You'll be notified when it's processed.\n"
        f"Request ID: {request_id}",
        reply_markup=reply_markup
    )

async def handle_admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin button clicks (approve/reject)."""
    query = update.callback_query
    
    # Handle verify membership callback
    if query.data == "verify_membership":
        user_id = update.effective_user.id
        if await check_user_membership(user_id, context, force_check=True):
            # Create keyboard with request channel button
            keyboard = [
                [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ Your membership has been verified! You can now use the bot.\n\n"
                "Send me a screenshot or image of the video/file you're looking for.",
                reply_markup=reply_markup
            )
        else:
            # Still not a member
            await query.answer("You need to join the channel first!", show_alert=True)
        return
    
    await query.answer()
    
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await query.edit_message_reply_markup(reply_markup=None)
        return
    
    # Parse callback data
    data = query.data.split("_")
    action = data[0]
    request_id = int(data[1])
    
    if request_id not in pending_requests:
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n⚠️ Error: Request not found in system",
            reply_markup=None
        )
        return
    
    request = pending_requests[request_id]
    user_id = request['user_id']
    
    if action == "approve":
        # Update request status
        pending_requests[request_id]['status'] = 'approved'
        
        # Update admin message
        keyboard = [
            [
                InlineKeyboardButton("Send File", callback_data=f"sendfile_{request_id}"),
                InlineKeyboardButton("Post to Channel", callback_data=f"postchannel_{request_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n✅ Approved by {user.mention_html()}",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        # Notify user
        keyboard = [
            [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Good news! Your request (ID: {request_id}) has been approved. "
                 f"The admin is preparing your file and will send it soon.",
            reply_markup=reply_markup
        )
        
    elif action == "reject":
        # Update request status
        pending_requests[request_id]['status'] = 'rejected'
        
        # Update admin message
        keyboard = [
            [InlineKeyboardButton("Send Reason", callback_data=f"sendreason_{request_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ Rejected by {user.mention_html()}",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        # Notify user
        keyboard = [
            [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Your request (ID: {request_id}) could not be fulfilled. "
                 f"An admin may provide more details soon.",
            reply_markup=reply_markup
        )
        
    elif action == "sendfile":
        # Ask admin to send the file
        context.user_data['sending_file_for'] = request_id
        
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n📤 Waiting for file from {user.mention_html()}...\n"
                   f"Please forward or upload the file as a reply to this message.",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        # Send instructions to admin in private
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Please send me the file for request ID: {request_id}.\n"
                 f"I'll forward it to the user who requested it."
        )
        
    elif action == "postchannel":
        # Ask admin to send the file to post to the channel
        context.user_data['posting_channel_for'] = request_id
        
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n📤 Waiting for file from {user.mention_html()} to post to channel...",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        # Send instructions to admin in private
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Please send me the file for request ID: {request_id} to post to the channel.\n"
                 f"You can also include a caption for the channel post."
        )
        
    elif action == "sendreason":
        # Ask admin to send rejection reason
        context.user_data['sending_reason_for'] = request_id
        
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n📝 Waiting for rejection reason from {user.mention_html()}...",
            reply_markup=None,
            parse_mode="HTML"
        )
        
        # Send instructions to admin in private
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Please send me the rejection reason for request ID: {request_id}.\n"
                 f"I'll forward it to the user who made the request."
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages from admins (file uploads or rejection reasons)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    # Check if we're waiting for a file or reason from this admin
    sending_file_for = context.user_data.get('sending_file_for')
    sending_reason_for = context.user_data.get('sending_reason_for')
    posting_channel_for = context.user_data.get('posting_channel_for')
    
    if sending_file_for and (update.message.document or update.message.video):
        request_id = sending_file_for
        if request_id not in pending_requests:
            await update.message.reply_text("Error: Request not found in system")
            return
        
        request = pending_requests[request_id]
        requester_id = request['user_id']
        
        # Forward the file to the requester
        caption = f"📁 Here's the file you requested (ID: {request_id})!"
        keyboard = [
            [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message.document:
            await context.bot.send_document(
                chat_id=requester_id,
                document=update.message.document.file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=requester_id,
                video=update.message.video.file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        
        # Update request status
        pending_requests[request_id]['status'] = 'completed'
        
        # Confirm to admin
        await update.message.reply_text(f"✅ File has been sent to the user for request ID: {request_id}")
        
        # Clear the context
        del context.user_data['sending_file_for']
        
    elif posting_channel_for and (update.message.document or update.message.video):
        request_id = posting_channel_for
        if request_id not in pending_requests:
            await update.message.reply_text("Error: Request not found in system")
            return
        
        request = pending_requests[request_id]
        requester_id = request['user_id']
        
        # Get requester username if possible
        try:
            requester = await context.bot.get_chat(requester_id)
            requester_username = requester.username
            requester_mention = f"@{requester_username}" if requester_username else f"User #{requester_id}"
        except Exception:
            requester_mention = f"User #{requester_id}"
        
        # Custom caption or default
        caption = update.message.caption or f"📁 Requested file (ID: {request_id})\nRequested by: {requester_mention}"
        
        # Post to the requests channel
        message_sent = None
        if update.message.document:
            message_sent = await context.bot.send_document(
                chat_id=REQUESTS_CHANNEL_ID,
                document=update.message.document.file_id,
                caption=caption
            )
        elif update.message.video:
            message_sent = await context.bot.send_video(
                chat_id=REQUESTS_CHANNEL_ID,
                video=update.message.video.file_id,
                caption=caption
            )
        
        # Update request status
        pending_requests[request_id]['status'] = 'posted_to_channel'
        
        # Also send to requester with link to the channel post
        if message_sent:
            post_link = f"https://t.me/{REQUIRED_CHANNEL_USERNAME}/{message_sent.message_id}"
            keyboard = [
                [InlineKeyboardButton("🔗 View in Channel", url=post_link)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message.document:
                await context.bot.send_document(
                    chat_id=requester_id,
                    document=update.message.document.file_id,
                    caption=f"📁 Here's the file you requested (ID: {request_id})!\nIt's also available in our channel.",
                    reply_markup=reply_markup
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=requester_id,
                    video=update.message.video.file_id,
                    caption=f"🎬 Here's the video you requested (ID: {request_id})!\nIt's also available in our channel.",
                    reply_markup=reply_markup
                )
        
        # Confirm to admin
        await update.message.reply_text(f"✅ File has been posted to the channel and sent to the user for request ID: {request_id}")
        
        # Clear the context
        del context.user_data['posting_channel_for']
        
    elif sending_reason_for and update.message.text:
        request_id = sending_reason_for
        if request_id not in pending_requests:
            await update.message.reply_text("Error: Request not found in system")
            return
        
        request = pending_requests[request_id]
        requester_id = request['user_id']
        reason = update.message.text
        
        # Send reason to the requester
        keyboard = [
            [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=requester_id,
            text=f"❌ Your request (ID: {request_id}) was rejected.\n\nReason: {reason}",
            reply_markup=reply_markup
        )
        
        # Update request status
        pending_requests[request_id]['status'] = 'rejected_with_reason'
        
        # Confirm to admin
        await update.message.reply_text(f"✅ Rejection reason has been sent to the user for request ID: {request_id}")
        
        # Clear the context
        del context.user_data['sending_reason_for']

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    user_id = update.effective_user.id
    
    # Check if user is a member of the required channel
    if not await check_user_membership(user_id, context):
        await send_join_requirement(update, context)
        return
        
    # If user sends text instead of image
    keyboard = [
        [InlineKeyboardButton("📹 Requested Videos Channel", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Please send a screenshot or image of the video/file you're looking for. "
        "Text requests are not supported.",
        reply_markup=reply_markup
    )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("verify", verify_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(handle_admin_button))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.PHOTO & ~filters.TEXT, handle_admin_message))
    
    # Track channel membership changes
    application.add_handler(ChatMemberHandler(track_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
