from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands
import os
import random
import asyncio
import json
from datetime import datetime, timedelta
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

class Tournament:
    def __init__(self):
        self.players = []
        self.max_players = 0
        self.active = False
        self.channel = None
        self.target_channel = None
        self.message = None
        self.rounds = []
        self.results = []
        self.fake_count = 1
        self.map = "BlockDash"
        self.abilities = "Punch, Spatula, Kick"
        self.mode = "1v1"
        self.prize = "Default"

tournament = Tournament()

# Store user data
user_data = {}
tickets = {}
warnings = {}
user_levels = {}
leveling_settings = {'enabled': False, 'channel': None}
welcomer_settings = {'enabled': False, 'channel': None}

# Load data
def load_data():
    global user_data, user_levels, leveling_settings, welcomer_settings
    try:
        with open('user_data.json', 'r') as f:
            data = json.load(f)
            user_data = data.get('user_data', {})
            user_levels = data.get('user_levels', {})
            leveling_settings = data.get('leveling_settings', {'enabled': False, 'channel': None})
            welcomer_settings = data.get('welcomer_settings', {'enabled': False, 'channel': None})
    except FileNotFoundError:
        pass

def save_data():
    data = {
        'user_data': user_data,
        'user_levels': user_levels,
        'leveling_settings': leveling_settings,
        'welcomer_settings': welcomer_settings
    }
    with open('user_data.json', 'w') as f:
        json.dump(data, f)

def add_xp(user_id, xp=1):
    if str(user_id) not in user_levels:
        user_levels[str(user_id)] = {'xp': 0, 'level': 1}
    
    user_levels[str(user_id)]['xp'] += xp
    
    # Calculate level (100 XP per level)
    new_level = (user_levels[str(user_id)]['xp'] // 100) + 1
    old_level = user_levels[str(user_id)]['level']
    
    if new_level > old_level:
        user_levels[str(user_id)]['level'] = new_level
        return True, new_level
    
    user_levels[str(user_id)]['level'] = new_level
    return False, new_level

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    load_data()
    # Don't add persistent views here - they'll be added when messages are sent
    print("🔧 Bot is ready and all systems operational!")

@bot.event
async def on_member_join(member):
    if welcomer_settings['enabled'] and welcomer_settings['channel']:
        channel = bot.get_channel(welcomer_settings['channel'])
        if channel:
            embed = discord.Embed(
                title="🎉 Welcome!",
                description=f"Welcome {member.mention} to **{member.guild.name}**!\n\nWe're happy to have you here! Make sure to read the rules and have fun!",
                color=0x00ff00
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Member #{len(member.guild.members)}")
            await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Add XP for messages if leveling is enabled
    if leveling_settings['enabled'] and leveling_settings['channel']:
        leveled_up, level = add_xp(message.author.id)
        if leveled_up:
            channel = bot.get_channel(leveling_settings['channel'])
            if channel:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} reached **Level {level}**!",
                    color=0xf1c40f
                )
                await channel.send(embed=embed)
        save_data()
    
    await bot.process_commands(message)

class TournamentConfigModal(discord.ui.Modal, title="Tournament Configuration"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    map_field = discord.ui.TextInput(
        label="🗺️ Map",
        placeholder="Enter map name...",
        default="BlockDash",
        max_length=50
    )

    abilities_field = discord.ui.TextInput(
        label="💥 Abilities",
        placeholder="Enter abilities...",
        default="Punch, Spatula, Kick",
        max_length=100
    )

    mode_field = discord.ui.TextInput(
        label="🎮 Mode",
        placeholder="Enter mode...",
        default="1v1",
        max_length=20
    )

    prize_field = discord.ui.TextInput(
        label="💶 Prize",
        placeholder="Enter prize...",
        default="Default",
        max_length=50
    )

    max_players_field = discord.ui.TextInput(
        label="👥 Max Players",
        placeholder="4, 8, or 16",
        default="8",
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_players = int(self.max_players_field.value)
            if max_players not in [4, 8, 16]:
                await interaction.response.send_message("❌ Max players must be 4, 8, or 16!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Max players must be a number!", ephemeral=True)
            return

        # Properly reset tournament
        tournament.__init__()
        tournament.max_players = max_players
        tournament.channel = self.target_channel
        tournament.target_channel = self.target_channel
        tournament.map = self.map_field.value
        tournament.abilities = self.abilities_field.value
        tournament.mode = self.mode_field.value
        tournament.prize = self.prize_field.value
        tournament.players = []  # Ensure players list is empty
        tournament.active = False  # Ensure tournament is not active

        embed = discord.Embed(title="🏆 Tournament Created!", color=0x00ff00)
        embed.add_field(name="🗺️ Map", value=tournament.map, inline=True)
        embed.add_field(name="💥 Abilities", value=tournament.abilities, inline=True)
        embed.add_field(name="🎮 Mode", value=tournament.mode, inline=True)
        embed.add_field(name="💶 Prize", value=tournament.prize, inline=True)
        embed.add_field(name="👥 Max Players", value=str(max_players), inline=True)

        embed.add_field(
            name="📜 Rules",
            value="🚫 No re-matches in case of bugs or technical issues.\n⏱️ You have 2 minutes to join.\n🤝 Teaming isn't allowed.\n🧑‍💻 Don't use hacks.",
            inline=False
        )

        view = TournamentView()
        # Update the participant count button to show correct max players
        for item in view.children:
            if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                item.label = f"0/{max_players}"
                break
        
        # Send tournament message
        tournament.message = await self.target_channel.send(embed=embed, view=view)
        
        # Respond with success
        await interaction.response.send_message("✅ Tournament created successfully!", ephemeral=True)
        
        print(f"✅ Tournament created: {max_players} max players, Map: {tournament.map}")

class TournamentConfigView(discord.ui.View):
    def __init__(self, target_channel):
        super().__init__(timeout=300)
        self.target_channel = target_channel

    @discord.ui.button(label="Set Tournament", style=discord.ButtonStyle.primary)
    async def set_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TournamentConfigModal(self.target_channel)
        await interaction.response.send_modal(modal)

class TournamentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Register", style=discord.ButtonStyle.green, custom_id="tournament_register")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check tournament state
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
            if tournament.active:
                return await interaction.response.send_message("⚠️ Tournament already started.", ephemeral=True)
            if interaction.user in tournament.players:
                return await interaction.response.send_message("❌ You are already registered.", ephemeral=True)
            if len(tournament.players) >= tournament.max_players:
                return await interaction.response.send_message("❌ Tournament is full.", ephemeral=True)

            # Add player
            tournament.players.append(interaction.user)
            
            # Update the participant count button
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                    item.label = f"{len(tournament.players)}/{tournament.max_players}"
                    break

            # Respond immediately to avoid timeout
            await interaction.response.edit_message(view=self)
            
            # Send confirmation
            await interaction.followup.send(f"✅ {interaction.user.display_name} registered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
            
        except discord.errors.NotFound:
            # Interaction expired - send new message
            await interaction.followup.send(f"✅ {interaction.user.display_name} registered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
        except Exception as e:
            print(f"Error in register_button: {e}")
            try:
                await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)

    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.red, custom_id="tournament_unregister")
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check tournament state
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
            if tournament.active:
                return await interaction.response.send_message("⚠️ Tournament already started.", ephemeral=True)
            if interaction.user not in tournament.players:
                return await interaction.response.send_message("❌ You are not registered.", ephemeral=True)

            # Remove player
            tournament.players.remove(interaction.user)
            
            # Update the participant count button
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                    item.label = f"{len(tournament.players)}/{tournament.max_players}"
                    break

            # Respond immediately to avoid timeout
            await interaction.response.edit_message(view=self)
            
            # Send confirmation
            await interaction.followup.send(f"✅ {interaction.user.display_name} unregistered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
            
        except discord.errors.NotFound:
            # Interaction expired - send new message
            await interaction.followup.send(f"✅ {interaction.user.display_name} unregistered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
        except Exception as e:
            print(f"Error in unregister_button: {e}")
            try:
                await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)

    @discord.ui.button(label="0/0", style=discord.ButtonStyle.secondary, disabled=True, custom_id="participant_count")
    async def participant_count(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🚀 Start Tournament", style=discord.ButtonStyle.primary, custom_id="start_tournament")
    async def start_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check permissions (optional - you can remove this if anyone should be able to start)
            if not interaction.user.guild_permissions.manage_channels:
                return await interaction.response.send_message("❌ You need 'Manage Channels' permission to start tournaments.", ephemeral=True)
            
            # Check if tournament exists and has been configured
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
                
            if tournament.active:
                return await interaction.response.send_message("❌ Tournament already started.", ephemeral=True)
                
            if len(tournament.players) < 2:
                return await interaction.response.send_message("❌ Not enough players to start tournament (minimum 2 players).", ephemeral=True)
            
            # Respond immediately to avoid timeout
            await interaction.response.send_message("🚀 Starting tournament...", ephemeral=True)
            
            # Add bot players if odd number of players
            if len(tournament.players) % 2 != 0:
                tournament.players.append(f"Bot{tournament.fake_count}")
                tournament.fake_count += 1

            # Set tournament as active and clear previous results
            tournament.active = True
            tournament.results = []
            tournament.rounds = []
            
            # Shuffle players for random matchups
            random.shuffle(tournament.players)

            # Create first round pairs
            round_pairs = [(tournament.players[i], tournament.players[i+1]) for i in range(0, len(tournament.players), 2)]
            tournament.rounds.append(round_pairs)

            # Create round 1 embed
            embed = discord.Embed(
                title="🏆 Tournament Started - Round 1", 
                description=f"**Map:** {tournament.map}\n**Mode:** {tournament.mode}\n**Abilities:** {tournament.abilities}",
                color=0x3498db
            )
            
            for i, (a, b) in enumerate(round_pairs, 1):
                player_a = getattr(a, 'display_name', a) if hasattr(a, 'display_name') else str(a)
                player_b = getattr(b, 'display_name', b) if hasattr(b, 'display_name') else str(b)
                embed.add_field(
                    name=f"⚔️ Match {i}", 
                    value=f"**{player_a}** vs **{player_b}**\n🏆 Winner: *Waiting...*", 
                    inline=False
                )

            embed.set_footer(text="Use !winner @player to record match results")
            
            # Send to the tournament channel
            tournament.message = await interaction.channel.send(embed=embed)
            
            # Send success confirmation
            await interaction.followup.send("✅ Tournament started successfully!", ephemeral=True)
            
        except Exception as e:
            print(f"Error in start_tournament: {e}")
            try:
                await interaction.response.send_message("❌ An error occurred while starting the tournament.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred while starting the tournament.", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        
        if not category:
            category = await guild.create_category("Tickets")

        ticket_channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        tickets[ticket_channel.id] = interaction.user.id

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Hello {interaction.user.mention}! Please describe your issue and wait for staff assistance.",
            color=0x00ff00
        )
        
        await ticket_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

class AccountModal(discord.ui.Modal, title="Link Your Account"):
    def __init__(self):
        super().__init__()

    ign_field = discord.ui.TextInput(
        label="🎮 In-Game Name",
        placeholder="Enter your in-game name...",
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_data[str(interaction.user.id)] = self.ign_field.value
        save_data()
        
        # Give linked role if it exists
        linked_role = discord.utils.get(interaction.guild.roles, name="🔗Linked")
        if linked_role and linked_role not in interaction.user.roles:
            try:
                await interaction.user.add_roles(linked_role)
                await interaction.response.send_message(f"✅ Account linked! IGN: `{self.ign_field.value}`\n🔗 You've been given the **Linked** role!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"✅ Account linked! IGN: `{self.ign_field.value}`\n⚠️ Couldn't give Linked role (insufficient permissions)", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Account linked! IGN: `{self.ign_field.value}`", ephemeral=True)

class AccountView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔗 Link Account", style=discord.ButtonStyle.primary, custom_id="link_account")
    async def link_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AccountModal()
        await interaction.response.send_modal(modal)

@bot.command()
async def create(ctx, channel: discord.TextChannel):
    try:
        await ctx.message.delete()
    except:
        pass
        
    tournament.target_channel = channel
    
    embed = discord.Embed(
        title="🏆 Tournament Setup",
        description="Press the button to configure the tournament settings.",
        color=0x00ff00
    )
    
    view = TournamentConfigView(channel)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def leveling_channel(ctx, channel: discord.TextChannel):
    try:
        await ctx.message.delete()
    except:
        pass
        
    leveling_settings['channel'] = channel.id
    save_data()
    await ctx.send(f"✅ Leveling channel set to {channel.mention}", delete_after=5)

@bot.command()
async def leveling_enable(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
        
    leveling_settings['enabled'] = not leveli
@bot.command()
async def delete_ticket(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
        
    if ctx.channel.id in tickets:
        await ctx.send("🗑️ Deleting ticket in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("❌ This is not a ticket channel.", delete_after=5)

@bot.command()
async def acc(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
        
    embed = discord.Embed(
        title="🔗 Account Linking",
        description="**Link your Discord account with your in-game profile!**\n\n🎮 **Why link your account?**\n• Access exclusive features\n• Participate in tournaments\n• Track your progress\n• Get personalized support\n\n📝 **Instructions:**\n• Click the button below\n• Enter your exact in-game name\n• Confirm the details\n\n🌟 **Ready to get started?**",
        color=0xe74c3c
    )
    embed.set_footer(text="Make sure to enter your exact IGN!")
    
    view = AccountView()
    await ctx.send(embed=embed, view=view)

@bot.command()
async def IGN(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except:
        pass
        
    if member is None:
        member = ctx.author
    
    if str(member.id) in user_data:
        embed = discord.Embed(
            title="🎮 Player Information",
            description=f"**Player:** {member.display_name}\n**IGN:** `{user_data[str(member.id)]}`",
            color=0x2ecc71
        )
        await ctx.send(embed=embed, delete_after=10)
    else:
        await ctx.send(f"❌ {member.display_name} hasn't linked their account yet.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await ctx.message.delete()
    except:
        pass
        
    if str(member.id) not in warnings:
        warnings[str(member.id)] = []
    
    warnings[str(member.id)].append({
        'reason': reason,
        'moderator': ctx.author.id,
        'timestamp': datetime.now().isoformat()
    })
    
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"**Member:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {ctx.author.mention}\n**Warnings:** {len(warnings[str(member.id)])}",
        color=0xf39c12
    )
    
    await ctx.send(embed=embed, delete_after=10)
    
    try:
        await member.send(f"⚠️ You have been warned in **{ctx.guild.name}**\n**Reason:** {reason}")
    except:
        pass
    
    embed.add_field(
        name="🏆 Tournament Commands",
        value="`!create #channel` - Create tournament\n`!start` - Start tournament\n`!winner @user` - Set round winner\n`!fake [number]` - Add 1-16 fake players (default: 1)\n`!cancel` - Cancel tournament\n`!code <code> @user` - Send match code via DM",
        inline=False
    )
    
    embed.add_field(
        name="📊 Leveling Commands",
        value="`!leveling_channel #channel` - Set level up channel\n`!leveling_enable` - Toggle leveling system\n`!level [@user]` - Check level (sent via DM)",
        inline=False
    )
    
    embed.add_field(
        name="👋 Welcomer Commands",
        value="`!welcomer_channel #channel` - Set welcome channel\n`!welcomer_enable` - Toggle welcomer system",
        inline=False
    )
    
    embed.add_field(
        name="🎫 Support Commands",
        value="`!ticket_panel` - Create ticket panel\n`!delete_ticket` - Delete current ticket",
        inline=False
    )
    
    embed.add_field(
        name="🔗 Account Commands",
        value="`!acc` - Account linking panel\n`!IGN [@user]` - Show IGN\n`!create_linked_role` - Create 🔗Linked role (auto-assigned when linking accounts)",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation Commands",
        value="`!warn @user [reason]` - Warn member\n`!mute @user <time> [reason]` - Mute member\n`!ban @user [time] [reason]` - Ban member\n`!lock` - Lock channel\n`!unlock` - Unlock channel",
        inline=False
    )
    
    embed.add_field(
        name="💬 Utility Commands",
        value="`!embed <text>` - Create embed\n`!commands` - Show this menu",
        inline=False
    )
    
    await ctx.send(embed=embed, delete_after=30)

@bot.command()
async def start(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Check if tournament exists and has been configured
    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament has been created yet. Use `!create #channel` first.", delete_after=5)
        
    if tournament.active:
        return await ctx.send("❌ Tournament already started.", delete_after=5)
        
    if len(tournament.players) < 2:
        return await ctx.send("❌ Not enough players to start tournament (minimum 2 players).", delete_after=5)
    
    # Add bot players if odd number of players
    if len(tournament.players) % 2 != 0:
        tournament.players.append(f"Bot{tournament.fake_count}")
        tournament.fake_count += 1

    # Set tournament as active and clear previous results
    tournament.active = True
    tournament.results = []
    tournament.rounds = []
    
    # Shuffle players for random matchups
    random.shuffle(tournament.players)

    # Create first round pairs
    round_pairs = [(tournament.players[i], tournament.players[i+1]) for i in range(0, len(tournament.players), 2)]
    tournament.rounds.append(round_pairs)

    # Create round 1 embed
    embed = discord.Embed(
        title="🏆 Tournament Started - Round 1", 
        description=f"**Map:** {tournament.map}\n**Mode:** {tournament.mode}\n**Abilities:** {tournament.abilities}",
        color=0x3498db
    )
    
    for i, (a, b) in enumerate(round_pairs, 1):
        player_a = getattr(a, 'display_name', a) if hasattr(a, 'display_name') else str(a)
        player_b = getattr(b, 'display_name', b) if hasattr(b, 'display_name') else str(b)
        embed.add_field(
            name=f"⚔️ Match {i}", 
            value=f"**{player_a}** vs **{player_b}**\n🏆 Winner: *Waiting...*", 
            inline=False
        )

    embed.set_footer(text="Use !winner @player to record match results")
    
    # Send to the tournament channel if it exists, otherwise current channel
    target_channel = tournament.target_channel if tournament.target_channel else ctx.channel
    tournament.message = await target_channel.send(embed=embed)
    
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Tournament started in {target_channel.mention}!", delete_after=5)

@bot.command()
async def winner(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass
        
    current_round = tournament.rounds[-1]
    winner_name = member.display_name
      except:
            pass
    
    await ctx.send(f"🤖 Added {number} fake player{'s' if number > 1 else ''}. Total players: {len(tournament.players)}/{tournament.max_players}", delete_after=5)

@bot.command()
async def code(ctx, code: str, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass
        
    try:
        await member.send(f"🔐 Match Code: `{code}`")
        await ctx.author.send(f"🔐 Match Code: `{code}` (sent to {member.display_name})")
        await ctx.send(f"✅ Code sent to {member.display_name} via DM!", delete_after=3)
    except:
        await ctx.send(f"❌ Could not send DM to {member.display_name}", delete_after=5)

@bot.command()
async def cancel(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
        
    tournament.__init__()
    await ctx.send("❌ Tournament cancelled.", delete_after=5)
from aiohttp import web
import asyncio
import os

async def handle(request):
    return web.Response(text="Bot is running!")

async def run_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    import discord
    from discord.ext import commands
    bot = commands.Bot(command_prefix="!")
    
    # !create,!code,!winner,!cancel,!ban,!warn,!mute,!lock,!unlock

    await run_webserver()
    await bot.start(os.getenv("TOKEN"))

asyncio.run(main())


