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
        self.teams = {}  # {user_id: team_partner_id}
        self.team_invites = {}  # {user_id: inviter_id}
        self.max_players = 0
        self.active = False
        self.channel = None
        self.target_channel = None
        self.message = None
        self.rounds = []
        self.results = []
        self.eliminated = []  # Track eliminated players for placement
        self.fake_count = 1
        self.map = ""
        self.abilities = ""
        self.mode = ""
        self.prize = ""
        self.title = ""

tournament = Tournament()

# Store user data
user_data = {}
tickets = {}
warnings = {}
user_levels = {}
tp_data = {}  # Tournament Points data
bracket_roles = {}  # {user_id: [emoji1, emoji2, emoji3]}
host_registrations = {'active': False, 'max_hosters': 0, 'hosters': [], 'channel': None, 'message': None}
leveling_settings = {'enabled': False, 'channel': None}
welcomer_settings = {'enabled': False, 'channel': None}

# TP Ranks
import discord
from discord.ext import commands
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

keep_alive()  # pornește serverul Flask

@bot.event
async def on_ready():
    print(f"✅ Botul e online ca {bot.user}")

bot.run(os.getenv("TOKEN"))
TP_RANKS = {
    'Wood': (0, 300),
    'Bronze': (301, 600),
    'Silver': (601, 900),
    'Gold': (901, 1200),
    'Platinum': (1201, 1500),
    'Master': (1501, 1800),
    'Champion': (1801, float('inf'))
}

def get_rank_from_tp(tp):
    for rank, (min_tp, max_tp) in TP_RANKS.items():
        if min_tp <= tp <= max_tp:
            return rank
    return 'Wood'

def get_player_display_name(player):
    """Get player display name with bracket roles (emojis) if set"""
    if isinstance(player, FakePlayer):
        return player.display_name
    
    if hasattr(player, 'nick') and player.nick:
        base_name = player.nick
    elif hasattr(player, 'display_name'):
        base_name = player.display_name
    else:
        base_name = str(player)
    
    # Add bracket role emojis if user has them (after name, not before)
    if hasattr(player, 'id') and str(player.id) in bracket_roles:
        emojis = ''.join(bracket_roles[str(player.id)])
        return f"{base_name} {emojis}"
    
    return base_name

# Load data
def load_data():
    global user_data, user_levels, leveling_settings, welcomer_settings, tp_data, bracket_roles
    try:
        with open('user_data.json', 'r') as f:
            data = json.load(f)
            user_data = data.get('user_data', {})
            user_levels = data.get('user_levels', {})
            tp_data = data.get('tp_data', {})
            bracket_roles = data.get('bracket_roles', {})
            leveling_settings = data.get('leveling_settings', {'enabled': False, 'channel': None})
            welcomer_settings = data.get('welcomer_settings', {'enabled': False, 'channel': None})
    except FileNotFoundError:
        pass

def save_data():
    data = {
        'user_data': user_data,
        'user_levels': user_levels,
        'tp_data': tp_data,
        'bracket_roles': bracket_roles,
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

def add_tp(user_id, tp):
    if str(user_id) not in tp_data:
        tp_data[str(user_id)] = 0
    tp_data[str(user_id)] += tp
    save_data()

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    load_data()
    
    # Add persistent views for buttons to work after restart
    bot.add_view(TournamentView())
    bot.add_view(TicketView())
    bot.add_view(AccountView())
    bot.add_view(TournamentConfigView(None))
    bot.add_view(HosterRegistrationView())
    
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

class TeamInviteView(discord.ui.View):
    def __init__(self, inviter_id, invited_id):
        super().__init__(timeout=300)
        self.inviter_id = inviter_id
        self.invited_id = invited_id

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept_invite(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invited_id:
            return await interaction.response.send_message("❌ This invite is not for you!", ephemeral=True)

        # Create team
        tournament.teams[self.inviter_id] = self.invited_id
        tournament.teams[self.invited_id] = self.inviter_id

        # Remove invite
        if self.invited_id in tournament.team_invites:
            del tournament.team_invites[self.invited_id]

        embed = discord.Embed(
            title="🤝 Team Formed!",
            description=f"<@{self.inviter_id}> and <@{self.invited_id}> are now teammates!",
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject_invite(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invited_id:
            return await interaction.response.send_message("❌ This invite is not for you!", ephemeral=True)

        # Remove invite
        if self.invited_id in tournament.team_invites:
            del tournament.team_invites[self.invited_id]

        embed = discord.Embed(
            title="❌ Invite Rejected",
            description=f"<@{self.invited_id}> rejected the team invitation.",
            color=0xff0000
        )
        await interaction.response.edit_message(embed=embed, view=None)

class TournamentConfigModal(discord.ui.Modal, title="Tournament Configuration"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    title_field = discord.ui.TextInput(
        label="🏆 Tournament Title",
        placeholder="Enter tournament title...",
        default="Stumble Guys Tournament",
        max_length=100
    )

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

    mode_and_players_field = discord.ui.TextInput(
        label="🎮 Mode & Max Players",
        placeholder="2v2 8 (format: mode maxplayers)",
        default="2v2 8",
        max_length=20
    )

    prize_field = discord.ui.TextInput(
        label="💶 Prize",
        placeholder="Enter prize...",
        default="Default",
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate target channel
            if not self.target_channel:
                await interaction.response.send_message("❌ Invalid target channel. Please try again.", ephemeral=True)
                return
            
            # Parse mode and max players
            mode_players_parts = self.mode_and_players_field.value.strip().split()
            if len(mode_players_parts) != 2:
                await interaction.response.send_message("❌ Format should be: mode maxplayers (e.g., '2v2 8')", ephemeral=True)
                return
                
            mode = mode_players_parts[0]
            max_players = int(mode_players_parts[1])
            
            if max_players not in [4, 8, 16, 32]:
                await interaction.response.send_message("❌ Max players must be 4, 8, 16 or 32!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Invalid format! Use: mode maxplayers (e.g., '2v2 8')", ephemeral=True)
            return
        except Exception as e:
            print(f"Error in tournament config modal: {e}")
            await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
            return

        # Properly reset tournament
        tournament.__init__()
        tournament.max_players = max_players
        tournament.channel = self.target_channel
        tournament.target_channel = self.target_channel
        tournament.title = self.title_field.value
        tournament.map = self.map_field.value
        tournament.abilities = self.abilities_field.value
        tournament.mode = mode
        tournament.prize = self.prize_field.value
        tournament.players = []
        tournament.teams = {}
        tournament.team_invites = {}
        tournament.eliminated = []
        tournament.active = False

        embed = discord.Embed(title=f"🏆 {tournament.title}", color=0x00ff00)
        embed.add_field(name="<:map:1407383523261677792> Map", value=tournament.map, inline=True)
        embed.add_field(name="<:abilities:1404513040505765939> Abilities", value=tournament.abilities, inline=True)
        embed.add_field(name="🎮 Mode", value=tournament.mode, inline=True)
        embed.add_field(name="<:gem:1407382933496533063> Prize", value=tournament.prize, inline=True)
        embed.add_field(name="👥 Max Players", value=str(max_players), inline=True)

        # Enhanced Stumble Guys rules with colors
        rules_text = (
            "🔹 **NO TEAMING** - Teams are only allowed in designated team modes\n"
            "🔸 **NO GRIEFING** - Don't intentionally sabotage other players\n"
            "🔹 **NO EXPLOITING** - Use of glitches or exploits will result in disqualification\n"
            "🔸 **FAIR PLAY** - Respect all players and play honorably\n"
            "🔹 **NO RAGE QUITTING** - Leaving mid-match counts as a forfeit\n"
            "🔸 **FOLLOW HOST** - Listen to tournament host instructions\n"
            "🔹 **NO TOXICITY** - Keep chat friendly and respectful\n"
            "🔸 **BE READY** - Join matches promptly when called\n"
            "🔹 **NO ALTS** - One account per player only"
        )

        embed.add_field(name="<:notr:1404513929522188329> **Stumble Guys Tournament Rules**", value=rules_text, inline=False)

        view = TournamentView()
        # Update the participant count button to show correct max players
        for item in view.children:
            if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                if tournament.mode == "2v2":
                    item.label = f"0 teams/{max_players//2}"
                else:
                    item.label = f"0/{max_players}"
                break

        # Send tournament message
        tournament.message = await self.target_channel.send(embed=embed, view=view)

        # Respond with success
        await interaction.response.send_message("✅ Tournament created successfully!", ephemeral=True)

        print(f"✅ Tournament created: {max_players} max players, Map: {tournament.map}")

class TournamentConfigView(discord.ui.View):
    def __init__(self, target_channel=None):
        super().__init__(timeout=None)
        self.target_channel = target_channel

    @discord.ui.button(label="Set Tournament", style=discord.ButtonStyle.primary, custom_id="set_tournament_config")
    async def set_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Use the channel where the interaction happened if no target channel is set
            target_channel = self.target_channel or interaction.channel
            
            # Ensure we have a valid channel
            if not target_channel:
                return await interaction.response.send_message("❌ Unable to determine target channel. Please try again.", ephemeral=True)
            
            modal = TournamentConfigModal(target_channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error in set_tournament: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception as follow_error:
                print(f"Failed to send error message: {follow_error}")

class TournamentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

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

            # For 2v2 mode, check team requirements
            if tournament.mode == "2v2":
                if interaction.user.id not in tournament.teams:
                    return await interaction.response.send_message("❌ You need a teammate to register for 2v2! Use `!invite @user` to invite someone.", ephemeral=True)

                teammate_id = tournament.teams[interaction.user.id]
                teammate = interaction.guild.get_member(teammate_id)

                if teammate in tournament.players:
                    return await interaction.response.send_message("❌ Your team is already registered.", ephemeral=True)

                if len(tournament.players) >= tournament.max_players:
                    return await interaction.response.send_message("❌ Tournament is full.", ephemeral=True)

                # Add both team members
                tournament.players.extend([interaction.user, teammate])

                # Update participant count for teams
                for item in self.children:
                    if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                        item.label = f"{len(tournament.players)//2} teams/{tournament.max_players//2}"
                        break

                await interaction.response.edit_message(view=self)
                await interaction.followup.send(f"✅ Team {interaction.user.display_name} & {teammate.display_name} registered! ({len(tournament.players)//2}/{tournament.max_players//2} teams)", ephemeral=True)

            else:
                # 1v1 mode
                if len(tournament.players) >= tournament.max_players:
                    return await interaction.response.send_message("❌ Tournament is full.", ephemeral=True)

                tournament.players.append(interaction.user)

                for item in self.children:
                    if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                        item.label = f"{len(tournament.players)}/{tournament.max_players}"
                        break

                await interaction.response.edit_message(view=self)
                await interaction.followup.send(f"✅ {interaction.user.display_name} registered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)

        except Exception as e:
            print(f"Error in register_button: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception as follow_error:
                print(f"Failed to send error message: {follow_error}")

    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.red, custom_id="tournament_unregister")
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
            if tournament.active:
                return await interaction.response.send_message("⚠️ Tournament already started.", ephemeral=True)
            if interaction.user not in tournament.players:
                return await interaction.response.send_message("❌ You are not registered.", ephemeral=True)

            if tournament.mode == "2v2":
                teammate_id = tournament.teams[interaction.user.id]
                teammate = interaction.guild.get_member(teammate_id)

                # Remove both team members
                if interaction.user in tournament.players:
                    tournament.players.remove(interaction.user)
                if teammate in tournament.players:
                    tournament.players.remove(teammate)

                for item in self.children:
                    if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                        item.label = f"{len(tournament.players)//2} teams/{tournament.max_players//2}"
                        break

                await interaction.response.edit_message(view=self)
                await interaction.followup.send(f"✅ Team {interaction.user.display_name} & {teammate.display_name} unregistered! ({len(tournament.players)//2}/{tournament.max_players//2} teams)", ephemeral=True)

            else:
                tournament.players.remove(interaction.user)

                for item in self.children:
                    if hasattr(item, 'custom_id') and item.custom_id == "participant_count":
                        item.label = f"{len(tournament.players)}/{tournament.max_players}"
                        break

                await interaction.response.edit_message(view=self)
                await interaction.followup.send(f"✅ {interaction.user.display_name} unregistered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)

        except Exception as e:
            print(f"Error in unregister_button: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception as follow_error:
                print(f"Failed to send error message: {follow_error}")

    @discord.ui.button(label="0/0", style=discord.ButtonStyle.secondary, disabled=True, custom_id="participant_count")
    async def participant_count(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🚀 Start Tournament", style=discord.ButtonStyle.primary, custom_id="start_tournament")
    async def start_tournament(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.user.guild_permissions.manage_channels:
                return await interaction.response.send_message("❌ You need 'Manage Channels' permission to start tournaments.", ephemeral=True)

            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)

            if tournament.active:
                return await interaction.response.send_message("❌ Tournament already started.", ephemeral=True)

            # Allow tournament to start even without max players
            if len(tournament.players) < 2:
                return await interaction.response.send_message("❌ Not enough players to start tournament (minimum 2 players).", ephemeral=True)

            await interaction.response.send_message("🚀 Starting tournament...", ephemeral=True)

            # Add bot players if needed for proper bracket
            while len(tournament.players) % 2 != 0:
                tournament.players.append(f"Bot{tournament.fake_count}")
                tournament.fake_count += 1

            tournament.active = True
            tournament.results = []
            tournament.rounds = []

            random.shuffle(tournament.players)

            if tournament.mode == "2v2":
                # Create team pairs for 2v2
                teams = []
                for i in range(0, len(tournament.players), 2):
                    teams.append((tournament.players[i], tournament.players[i+1]))

                round_pairs = [(teams[i], teams[i+1]) for i in range(0, len(teams), 2)]
            else:
                # Create individual pairs for 1v1
                round_pairs = [(tournament.players[i], tournament.players[i+1]) for i in range(0, len(tournament.players), 2)]

            tournament.rounds.append(round_pairs)

            embed = discord.Embed(
                title=f"🏆 {tournament.title} - Round 1", 
                description=f"**Map:** {tournament.map}\n**Mode:** {tournament.mode}\n**Abilities:** {tournament.abilities}",
                color=0x3498db
            )

            for i, match in enumerate(round_pairs, 1):
                if tournament.mode == "2v2":
                    team_a, team_b = match
                    team_a_str = f"{get_player_display_name(team_a[0])} & {get_player_display_name(team_a[1])}"
                    team_b_str = f"{get_player_display_name(team_b[0])} & {get_player_display_name(team_b[1])}"
                    embed.add_field(
                        name=f"⚔️ Match {i}", 
                        value=f"**{team_a_str}** <:vs:1407383732889059359> **{team_b_str}**\n<:crown:1404513986887553157> Winner: *Waiting...*", 
                        inline=False
                    )
                else:
                    a, b = match
                    player_a = get_player_display_name(a)
                    player_b = get_player_display_name(b)
                    embed.add_field(
                        name=f"⚔️ Match {i}", 
                        value=f"**{player_a}** <:vs:1407383732889059359> **{player_b}**\n<:crown:1404513986887553157> Winner: *Waiting...*", 
                        inline=False
                    )

            embed.set_footer(text="Use !winner @player to record match results")

            tournament.message = await interaction.channel.send(embed=embed)
            await interaction.followup.send("✅ Tournament started successfully!", ephemeral=True)

        except Exception as e:
            print(f"Error in start_tournament: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while starting the tournament.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred while starting the tournament.", ephemeral=True)
            except Exception as follow_error:
                print(f"Failed to send error message: {follow_error}")

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

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
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="🔗 Link Account", style=discord.ButtonStyle.primary, custom_id="link_account")
    async def link_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AccountModal()
        await interaction.response.send_modal(modal)

@bot.command()
async def invite(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass

    if tournament.mode != "2v2":
        return await ctx.send("❌ Team invites are only available in 2v2 mode.", delete_after=5)

    if ctx.author.id in tournament.teams:
        return await ctx.send("❌ You already have a teammate.", delete_after=5)

    if member.id in tournament.teams:
        return await ctx.send("❌ This user already has a teammate.", delete_after=5)

    if member.id in tournament.team_invites:
        return await ctx.send("❌ This user already has a pending invite.", delete_after=5)

    if member.bot:
        return await ctx.send("❌ You cannot invite bots as teammates.", delete_after=5)

    tournament.team_invites[member.id] = ctx.author.id

    embed = discord.Embed(
        title="🤝 Team Invitation",
        description=f"{ctx.author.mention} invited you to be their teammate!",
        color=0x3498db
    )

    view = TeamInviteView(ctx.author.id, member.id)

    try:
        await member.send(embed=embed, view=view)
        await ctx.send(f"✅ Team invitation sent to {member.display_name}!", delete_after=5)
    except discord.Forbidden:
        await ctx.send(f"❌ Could not send DM to {member.display_name}. They may have DMs disabled.", delete_after=5)

@bot.command()
async def leave_team(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    if ctx.author.id not in tournament.teams:
        return await ctx.send("❌ You don't have a teammate.", delete_after=5)

    teammate_id = tournament.teams[ctx.author.id]
    teammate = ctx.guild.get_member(teammate_id)

    # Remove from teams
    del tournament.teams[ctx.author.id]
    del tournament.teams[teammate_id]

    # Unregister team if registered
    if ctx.author in tournament.players:
        tournament.players.remove(ctx.author)
    if teammate in tournament.players:
        tournament.players.remove(teammate)

    await ctx.send(f"✅ You left the team with {teammate.display_name}. Your team has been unregistered from the tournament.", delete_after=10)

@bot.command()
async def tp(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except:
        pass

    if member is None:
        member = ctx.author

    tp = tp_data.get(str(member.id), 0)
    rank = get_rank_from_tp(tp)

    embed = discord.Embed(
        title="🏆 Tournament Points",
        description=f"**Player:** {member.display_name}\n**TP:** {tp}\n**Rank:** {rank}",
        color=0xe74c3c
    )

    try:
        await ctx.author.send(embed=embed)
        await ctx.send("📨 TP information sent via DM!", delete_after=3)
    except discord.Forbidden:
        await ctx.send(embed=embed, delete_after=10)

@bot.command()
async def tplb(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    # Sort players by TP
    sorted_players = sorted(tp_data.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Tournament Points Leaderboard",
        color=0xf1c40f
    )

    if not sorted_players:
        embed.description = "No players have TP yet!"
    else:
        leaderboard_text = ""
        for i, (user_id, tp) in enumerate(sorted_players, 1):
            user = ctx.guild.get_member(int(user_id))
            if user:
                rank = get_rank_from_tp(tp)
                leaderboard_text += f"**{i}.** {user.display_name} - **{rank.upper()}**: {tp} TP\n"

        embed.description = leaderboard_text

    await ctx.send(embed=embed, delete_after=30)

@bot.command()
@commands.has_permissions(administrator=True)
async def tprst(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    tp_data.clear()
    save_data()
    await ctx.send("✅ All Tournament Points have been reset!", delete_after=5)

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

    leveling_settings['enabled'] = not leveling_settings['enabled']
    status = "enabled" if leveling_settings['enabled'] else "disabled"
    save_data()
    await ctx.send(f"✅ Leveling system {status}!", delete_after=5)

@bot.command()
async def welcomer_channel(ctx, channel: discord.TextChannel):
    try:
        await ctx.message.delete()
    except:
        pass

    welcomer_settings['channel'] = channel.id
    save_data()
    await ctx.send(f"✅ Welcomer channel set to {channel.mention}", delete_after=5)

@bot.command()
async def welcomer_enable(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    welcomer_settings['enabled'] = not welcomer_settings['enabled']
    status = "enabled" if welcomer_settings['enabled'] else "disabled"
    save_data()
    await ctx.send(f"✅ Welcomer system {status}!", delete_after=5)

@bot.command()
async def ticket_panel(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="**Need help?**\n\nClick the button below to create a support ticket. Our staff will assist you as soon as possible!\n\n🔹 **What can we help with?**\n• Technical issues\n• Account problems\n• General questions\n• Report bugs\n• Other concerns",
        color=0x3498db
    )
    embed.set_footer(text="Tickets are private and only visible to you and staff")

    view = TicketView()
    await ctx.send(embed=embed, view=view)

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

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn_hs(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass

    user_warnings = warnings.get(str(member.id), [])

    embed = discord.Embed(
        title="⚠️ Warning History",
        description=f"**Member:** {member.mention}\n**Total Warnings:** {len(user_warnings)}",
        color=0xf39c12
    )

    if user_warnings:
        for i, warning in enumerate(user_warnings[-5:], 1):  # Show last 5 warnings
            moderator = ctx.guild.get_member(warning['moderator'])
            mod_name = moderator.display_name if moderator else "Unknown"
            timestamp = datetime.fromisoformat(warning['timestamp']).strftime("%Y-%m-%d %H:%M")
            embed.add_field(
                name=f"Warning #{len(user_warnings) - 5 + i}",
                value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod_name}\n**Date:** {timestamp}",
                inline=False
            )
    else:
        embed.add_field(name="No Warnings", value="This user has no warnings.", inline=False)

    await ctx.send(embed=embed, delete_after=20)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warnrmv(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass

    if str(member.id) in warnings:
        del warnings[str(member.id)]
        await ctx.send(f"✅ All warnings removed for {member.display_name}!", delete_after=5)
    else:
        await ctx.send(f"❌ {member.display_name} has no warnings to remove.", delete_after=5)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, time: str, *, reason="No reason provided"):
    try:
        await ctx.message.delete()
    except:
        pass

    # Parse time (e.g., "1h", "30m", "2d")
    time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    time_amount = int(time[:-1])
    time_unit = time[-1].lower()

    if time_unit not in time_units:
        return await ctx.send("❌ Invalid time format! Use s/m/h/d (e.g., 30m, 2h, 1d)", delete_after=5)

    duration = timedelta(seconds=time_amount * time_units[time_unit])

    try:
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(
            title="🔇 Member Muted",
            description=f"**Member:** {member.mention}\n**Duration:** {time}\n**Reason:** {reason}\n**Moderator:** {ctx.author.mention}",
            color=0xf39c12
        )
        await ctx.send(embed=embed, delete_after=15)

        try:
            await member.send(f"🔇 You have been muted in **{ctx.guild.name}** for {time}\n**Reason:** {reason}")
        except:
            pass

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to mute this member.", delete_after=5)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass

    try:
        await member.timeout(None)
        embed = discord.Embed(
            title="🔊 Member Unmuted",
            description=f"**Member:** {member.mention}\n**Moderator:** {ctx.author.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed, delete_after=10)

        try:
            await member.send(f"🔊 You have been unmuted in **{ctx.guild.name}**")
        except:
            pass

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unmute this member.", delete_after=5)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, time: str = None, *, reason="No reason provided"):
    try:
        await ctx.message.delete()
    except:
        pass

    try:
        await member.send(f"🔨 You have been banned from **{ctx.guild.name}**\n**Reason:** {reason}")
    except:
        pass

    await member.ban(reason=reason)

    embed = discord.Embed(
        title="🔨 Member Banned",
        description=f"**Member:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {ctx.author.mention}",
        color=0xe74c3c
    )

    if time:
        embed.add_field(name="Duration", value=time, inline=True)

    await ctx.send(embed=embed, delete_after=15)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        await ctx.message.delete()
    except:
        pass

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)

        embed = discord.Embed(
            title="🔓 Member Unbanned",
            description=f"**Member:** {user.mention}\n**Moderator:** {ctx.author.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed, delete_after=10)

    except discord.NotFound:
        await ctx.send("❌ User not found or not banned.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban members.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    embed = discord.Embed(
        title="🔒 Channel Locked",
        description=f"This channel has been locked by {ctx.author.mention}",
        color=0xe74c3c
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
    embed = discord.Embed(
        title="🔓 Channel Unlocked",
        description=f"This channel has been unlocked by {ctx.author.mention}",
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

@bot.command()
async def embed(ctx, *, text):
    try:
        await ctx.message.delete()
    except:
        pass

    embed = discord.Embed(description=text, color=0x3498db)
    await ctx.send(embed=embed)

@bot.command()
async def level(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except:
        pass

    if member is None:
        member = ctx.author

    if str(member.id) in user_levels:
        level_data = user_levels[str(member.id)]
        embed = discord.Embed(
            title="📊 Level Information",
            description=f"**Player:** {member.display_name}\n**Level:** {level_data['level']}\n**XP:** {level_data['xp']}\n**Next Level:** {(level_data['level'] * 100) - level_data['xp']} XP needed",
            color=0xf1c40f
        )
    else:
        embed = discord.Embed(
            title="📊 Level Information",
            description=f"**Player:** {member.display_name}\n**Level:** 1\n**XP:** 0\n**Next Level:** 100 XP needed",
            color=0xf1c40f
        )

    try:
        await ctx.author.send(embed=embed)
        await ctx.send("📨 Level information sent via DM!", delete_after=3)
    except discord.Forbidden:
        await ctx.send(embed=embed, delete_after=10)

@bot.command()
async def create_linked_role(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    if discord.utils.get(ctx.guild.roles, name="🔗Linked"):
        return await ctx.send("❌ 🔗Linked role already exists!", delete_after=5)

    try:
        await ctx.guild.create_role(name="🔗Linked", color=0x00ff00)
        await ctx.send("✅ 🔗Linked role created successfully!", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to create roles.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def bracketrole(ctx, emoji1: str, emoji2: str = "", emoji3: str = ""):
    try:
        await ctx.message.delete()
    except:
        pass

    emojis = [emoji1, emoji2, emoji3]
    # Filter out empty emojis
    emojis = [e for e in emojis if e.strip()]
    
    if len(emojis) > 3:
        return await ctx.send("❌ You can only set up to 3 emojis!", delete_after=5)
    
    if len(emojis) == 0:
        return await ctx.send("❌ You must provide at least one emoji!", delete_after=5)

    bracket_roles[str(ctx.author.id)] = emojis
    save_data()
    
    emoji_display = ''.join(emojis)
    player_name = ctx.author.nick if ctx.author.nick else ctx.author.display_name
    
    await ctx.send(f"✅ Bracket role set! Your bracket name: {player_name} {emoji_display}", delete_after=10)

@bot.command()
async def bracketname(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    if str(ctx.author.id) in bracket_roles:
        emojis = ''.join(bracket_roles[str(ctx.author.id)])
        player_name = ctx.author.nick if ctx.author.nick else ctx.author.display_name
        bracket_name = f"{emojis} {player_name}"
    else:
        player_name = ctx.author.nick if ctx.author.nick else ctx.author.display_name
        bracket_name = player_name

    embed = discord.Embed(
        title="🏷️ Your Bracket Name",
        description=f"**Bracket Name:** {bracket_name}",
        color=0x3498db
    )
    
    try:
        await ctx.author.send(embed=embed)
        await ctx.send("📨 Bracket name sent via DM!", delete_after=3)
    except discord.Forbidden:
        await ctx.send(embed=embed, delete_after=10)

@bot.command()
async def bracketrolereset(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    if str(ctx.author.id) in bracket_roles:
        del bracket_roles[str(ctx.author.id)]
        save_data()
        await ctx.send("✅ Bracket role reset! Your emojis have been removed.", delete_after=5)
    else:
        await ctx.send("❌ You don't have any bracket emojis set.", delete_after=5)

class HosterRegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="Register", style=discord.ButtonStyle.green, custom_id="hoster_register")
    async def register_hoster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not host_registrations['active']:
            return await interaction.response.send_message("❌ Hoster registration is not active.", ephemeral=True)

        if interaction.user in host_registrations['hosters']:
            return await interaction.response.send_message("❌ You are already registered as a hoster.", ephemeral=True)

        if len(host_registrations['hosters']) >= host_registrations['max_hosters']:
            return await interaction.response.send_message("❌ Maximum number of hosters reached.", ephemeral=True)

        host_registrations['hosters'].append(interaction.user)
        
        # Update the embed
        embed = discord.Embed(
            title="🎯 Hoster Registration",
            description="Here the hosters will register to host tournaments!",
            color=0x00ff00
        )
        
        if host_registrations['hosters']:
            hoster_list = ""
            for i, hoster in enumerate(host_registrations['hosters'], 1):
                hoster_name = hoster.nick if hoster.nick else hoster.display_name
                hoster_list += f"{i}. {hoster_name}\n"
            embed.add_field(name="Hosters registered:", value=hoster_list, inline=False)
        else:
            embed.add_field(name="Hosters registered:", value="None yet", inline=False)
        
        embed.add_field(name="Slots:", value=f"{len(host_registrations['hosters'])}/{host_registrations['max_hosters']}", inline=True)

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.display_name} registered as a hoster!", ephemeral=True)

    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.red, custom_id="hoster_unregister")
    async def unregister_hoster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not host_registrations['active']:
            return await interaction.response.send_message("❌ Hoster registration is not active.", ephemeral=True)

        if interaction.user not in host_registrations['hosters']:
            return await interaction.response.send_message("❌ You are not registered as a hoster.", ephemeral=True)

        host_registrations['hosters'].remove(interaction.user)
        
        # Update the embed
        embed = discord.Embed(
            title="🎯 Hoster Registration",
            description="Here the hosters will register to host tournaments!",
            color=0x00ff00
        )
        
        if host_registrations['hosters']:
            hoster_list = ""
            for i, hoster in enumerate(host_registrations['hosters'], 1):
                hoster_name = hoster.nick if hoster.nick else hoster.display_name
                hoster_list += f"{i}. {hoster_name}\n"
            embed.add_field(name="Hosters registered:", value=hoster_list, inline=False)
        else:
            embed.add_field(name="Hosters registered:", value="None yet", inline=False)
        
        embed.add_field(name="Slots:", value=f"{len(host_registrations['hosters'])}/{host_registrations['max_hosters']}", inline=True)

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.display_name} unregistered from hosting.", ephemeral=True)

    @discord.ui.button(label="End Register", style=discord.ButtonStyle.secondary, custom_id="end_hoster_register")
    async def end_registration(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need 'Manage Channels' permission to end registration.", ephemeral=True)

        host_registrations['active'] = False
        
        # Keep the existing embed but disable all buttons
        embed = discord.Embed(
            title="🎯 Hoster Registration - CLOSED",
            description="Hoster registration has been closed by a moderator.",
            color=0xff0000
        )
        
        if host_registrations['hosters']:
            hoster_list = ""
            for i, hoster in enumerate(host_registrations['hosters'], 1):
                hoster_name = hoster.nick if hoster.nick else hoster.display_name
                hoster_list += f"{i}. {hoster_name}\n"
            embed.add_field(name="Final Hosters registered:", value=hoster_list, inline=False)
        else:
            embed.add_field(name="Final Hosters registered:", value="None", inline=False)
        
        embed.add_field(name="Final Slots:", value=f"{len(host_registrations['hosters'])}/{host_registrations['max_hosters']}", inline=True)

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

@bot.command()
async def hosterregist(ctx, max_hosters: int):
    try:
        await ctx.message.delete()
    except:
        pass

    if not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You need 'Manage Channels' permission to start hoster registration.", delete_after=5)

    if max_hosters < 1 or max_hosters > 20:
        return await ctx.send("❌ Maximum hosters must be between 1 and 20.", delete_after=5)

    host_registrations['active'] = True
    host_registrations['max_hosters'] = max_hosters
    host_registrations['hosters'] = []
    host_registrations['channel'] = ctx.channel

    embed = discord.Embed(
        title="🎯 Hoster Registration",
        description="Here the hosters will register to host tournaments!",
        color=0x00ff00
    )
    
    embed.add_field(name="Hosters registered:", value="None yet", inline=False)
    embed.add_field(name="Slots:", value=f"0/{max_hosters}", inline=True)

    view = HosterRegistrationView()
    host_registrations['message'] = await ctx.send(embed=embed, view=view)

@bot.command()
async def commands(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=0x3498db
    )

    # Show admin commands only to users with manage_channels permission
    if ctx.author.guild_permissions.manage_channels:
        embed.add_field(
            name="🏆 Tournament Commands (Admin)",
            value="`!create #channel` - Create tournament\n`!start` - Start tournament\n`!winner @user` - Set round winner\n`!fake [number]` - Add 1-16 fake players (default: 1)\n`!cancel` - Cancel tournament\n`!code <code> @user` - Send match code via DM",
            inline=False
        )

        embed.add_field(
            name="🛡️ Moderation Commands (Admin)",
            value="`!warn @user [reason]` - Warn member\n`!warn_hs @user` - Show warning history\n`!warnrmv @user` - Remove all warnings\n`!mute @user <time> [reason]` - Mute member\n`!unmute @user` - Unmute member\n`!ban @user [time] [reason]` - Ban member\n`!unban <user_id>` - Unban member\n`!lock` - Lock channel\n`!unlock` - Unlock channel",
            inline=False
        )

        embed.add_field(
            name="📊 System Commands (Admin)",
            value="`!leveling_channel #channel` - Set level up channel\n`!leveling_enable` - Toggle leveling system\n`!welcomer_channel #channel` - Set welcome channel\n`!welcomer_enable` - Toggle welcomer system\n`!tprst` - Reset all Tournament Points",
            inline=False
        )

        embed.add_field(
            name="🎫 Support Commands (Admin)",
            value="`!ticket_panel` - Create ticket panel\n`!delete_ticket` - Delete current ticket",
            inline=False
        )

        embed.add_field(
            name="🎯 Hoster Registration (Admin)",
            value="`!hosterregist <max_hosters>` - Create hoster registration panel",
            inline=False
        )

        embed.add_field(
            name="🏷️ Bracket Management (Admin)",
            value="`!bracketrole emoji1 [emoji2] [emoji3]` - Set bracket emojis for users",
            inline=False
        )

        embed.add_field(
            name="🔗 Account Commands (Admin)",
            value="`!acc` - Account linking panel\n`!IGN [@user]` - Show IGN\n`!level [@user]` - Check level (sent via DM)",
            inline=False
        )

        embed.add_field(
            name="💬 Utility Commands (Admin)",
            value="`!embed <text>` - Create embed\n`!commands` - Show this menu",
            inline=False
        )

    # Member commands (always visible to everyone)
    embed.add_field(
        name="🤝 Team Commands",
        value="`!invite @user` - Invite user to team (2v2 mode)\n`!leave_team` - Leave current team",
        inline=False
    )

    embed.add_field(
        name="🏆 Tournament Points",
        value="`!tp [@user]` - Check Tournament Points\n`!tplb` - View TP leaderboard",
        inline=False
    )
    
    embed.add_field(
        name="🏷️ Bracket Display",
        value="`!bracketname` - Show your bracket name\n`!bracketrolereset` - Reset bracket emojis",
        inline=False
    )

    await ctx.send(embed=embed, delete_after=30)

@bot.command()
async def start(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament has been created yet. Use `!create #channel` first.", delete_after=5)

    if tournament.active:
        return await ctx.send("❌ Tournament already started.", delete_after=5)

    if len(tournament.players) < 2:
        return await ctx.send("❌ Not enough players to start tournament (minimum 2 players).", delete_after=5)

    # Add bot players if needed for proper bracket
    while len(tournament.players) % 2 != 0:
        fake_name = f"Bot{tournament.fake_count}"
        fake_id = 761557952975420886 + tournament.fake_count
        fake_player = FakePlayer(fake_name, fake_id)
        tournament.players.append(fake_player)
        tournament.fake_count += 1

    tournament.active = True
    tournament.results = []
    tournament.rounds = []

    random.shuffle(tournament.players)

    if tournament.mode == "2v2":
        teams = []
        for i in range(0, len(tournament.players), 2):
            teams.append((tournament.players[i], tournament.players[i+1]))

        round_pairs = [(teams[i], teams[i+1]) for i in range(0, len(teams), 2)]
    else:
        round_pairs = [(tournament.players[i], tournament.players[i+1]) for i in range(0, len(tournament.players), 2)]

    tournament.rounds.append(round_pairs)

    embed = discord.Embed(
        title=f"🏆 {tournament.title} - Round 1", 
        description=f"**Map:** {tournament.map}\n**Mode:** {tournament.mode}\n**Abilities:** {tournament.abilities}",
        color=0x3498db
    )

    for i, match in enumerate(round_pairs, 1):
        if tournament.mode == "2v2":
            team_a, team_b = match
            team_a_str = f"{getattr(team_a[0], 'display_name', team_a[0])} & {getattr(team_a[1], 'display_name', team_a[1])}"
            team_b_str = f"{getattr(team_b[0], 'display_name', team_b[0])} & {getattr(team_b[1], 'display_name', team_b[1])}"
            embed.add_field(
                name=f"⚔️ Match {i}", 
                value=f"**{team_a_str}** vs **{team_b_str}**\n🏆 Winner: *Waiting...*", 
                inline=False
            )
        else:
            a, b = match
            player_a = getattr(a, 'display_name', a) if hasattr(a, 'display_name') else str(a)
            player_b = getattr(b, 'display_name', b) if hasattr(b, 'display_name') else str(b)
            embed.add_field(
                name=f"⚔️ Match {i}", 
                value=f"**{player_a}** vs **{player_b}**\n🏆 Winner: *Waiting...*", 
                inline=False
            )

    embed.set_footer(text="Use !winner @player to record match results")

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

    if not tournament.active:
        return await ctx.send("❌ No active tournament.", delete_after=5)

    current_round = tournament.rounds[-1]
    winner_name = member.display_name

    # Find and update the match
    match_found = False
    eliminated_players = []
    
    for i, match in enumerate(current_round):
        if tournament.mode == "2v2":
            team_a, team_b = match
            if member in [team_a[0], team_a[1], team_b[0], team_b[1]]:
                # Update match result
                if member in [team_a[0], team_a[1]]:
                    tournament.results.append(team_a)
                    eliminated_players.extend([team_b[0], team_b[1]])
                else:
                    tournament.results.append(team_b)
                    eliminated_players.extend([team_a[0], team_a[1]])
                match_found = True
                break
        else:
            a, b = match
            if member in [a, b]:
                tournament.results.append(member)
                eliminated_players.append(a if member == b else b)
                match_found = True
                break

    if not match_found:
        return await ctx.send("❌ This player is not in the current round.", delete_after=5)

    # Add eliminated players to elimination list
    tournament.eliminated.extend(eliminated_players)

    # Check if round is complete
    if len(tournament.results) == len(current_round):
        if len(tournament.results) == 1:
            # Tournament finished - determine placements and award TP
            winner = tournament.results[0]
            
            # Calculate placements based on elimination order
            # Last eliminated = 2nd place, second-to-last batch = 3rd/4th place
            all_eliminated = tournament.eliminated
            
            # Get the final 4 placements
            if tournament.mode == "2v2":
                # For teams
                placements = []
                
                # 1st place (winner)
                placements.append((1, winner, 100))
                
                # 2nd place (last eliminated team - should be 2 players)
                if len(all_eliminated) >= 2:
                    second_place = (all_eliminated[-2], all_eliminated[-1])
                    placements.append((2, second_place, 70))
                
                # 3rd and 4th place (previous eliminations)
                remaining_eliminated = all_eliminated[:-2] if len(all_eliminated) >= 2 else []
                if len(remaining_eliminated) >= 4:
                    third_place = (remaining_eliminated[-4], remaining_eliminated[-3])
                    fourth_place = (remaining_eliminated[-2], remaining_eliminated[-1])
                    placements.append((3, third_place, 50))
                    placements.append((4, fourth_place, 50))
                elif len(remaining_eliminated) >= 2:
                    third_place = (remaining_eliminated[-2], remaining_eliminated[-1])
                    placements.append((3, third_place, 50))
                
                # Award TP and create results message
                results_text = ""
                for place, team, tp in placements:
                    if place == 1:
                        emoji = "🥇"
                        team_str = f"{get_player_display_name(team[0])} & {get_player_display_name(team[1])}"
                        # Award TP to both team members
                        if hasattr(team[0], 'id') and not isinstance(team[0], FakePlayer):
                            add_tp(team[0].id, tp)
                        if hasattr(team[1], 'id') and not isinstance(team[1], FakePlayer):
                            add_tp(team[1].id, tp)
                    elif place == 2:
                        emoji = "🥈"
                        team_str = f"{get_player_display_name(team[0])} & {get_player_display_name(team[1])}"
                        if hasattr(team[0], 'id') and not isinstance(team[0], FakePlayer):
                            add_tp(team[0].id, tp)
                        if hasattr(team[1], 'id') and not isinstance(team[1], FakePlayer):
                            add_tp(team[1].id, tp)
                    elif place == 3:
                        emoji = "🥉"
                        team_str = f"{get_player_display_name(team[0])} & {get_player_display_name(team[1])}"
                        if hasattr(team[0], 'id') and not isinstance(team[0], FakePlayer):
                            add_tp(team[0].id, tp)
                        if hasattr(team[1], 'id') and not isinstance(team[1], FakePlayer):
                            add_tp(team[1].id, tp)
                    else:
                        emoji = "4️⃣"
                        team_str = f"{get_player_display_name(team[0])} & {get_player_display_name(team[1])}"
                        if hasattr(team[0], 'id') and not isinstance(team[0], FakePlayer):
                            add_tp(team[0].id, tp)
                        if hasattr(team[1], 'id') and not isinstance(team[1], FakePlayer):
                            add_tp(team[1].id, tp)
                    
                    results_text += f"{emoji} {team_str} - {tp} TP\n"
                
            else:
                # For individual players
                placements = []
                
                # 1st place (winner)
                placements.append((1, winner, 100))
                
                # 2nd place (last eliminated)
                if len(all_eliminated) >= 1:
                    placements.append((2, all_eliminated[-1], 70))
                
                # 3rd and 4th place
                if len(all_eliminated) >= 2:
                    placements.append((3, all_eliminated[-2], 50))
                if len(all_eliminated) >= 3:
                    placements.append((4, all_eliminated[-3], 50))
                
                # Award TP and create results message
                results_text = ""
                for place, player, tp in placements:
                    if place == 1:
                        emoji = "🥇"
                    elif place == 2:
                        emoji = "🥈"
                    elif place == 3:
                        emoji = "🥉"
                    else:
                        emoji = "4️⃣"
                    
                    player_name = get_player_display_name(player)
                    if hasattr(player, 'id') and not isinstance(player, FakePlayer):
                        add_tp(player.id, tp)
                    
                    results_text += f"{emoji} {player_name} - {tp} TP\n"

            embed = discord.Embed(
                title="🏆 Tournament Complete!",
                description=f"**Final Results:**\n\n{results_text}",
                color=0xffd700
            )
            await ctx.send(embed=embed)

            # Reset tournament
            tournament.__init__()
        else:
            # Create next round
            next_round_pairs = []
            if tournament.mode == "2v2":
                teams = tournament.results
                for i in range(0, len(teams), 2):
                    if i + 1 < len(teams):
                        next_round_pairs.append((teams[i], teams[i+1]))
            else:
                for i in range(0, len(tournament.results), 2):
                    if i + 1 < len(tournament.results):
                        next_round_pairs.append((tournament.results[i], tournament.results[i+1]))

            tournament.rounds.append(next_round_pairs)
            tournament.results = []

            round_num = len(tournament.rounds)
            embed = discord.Embed(
                title=f"🏆 {tournament.title} - Round {round_num}",
                description=f"**Map:** {tournament.map}\n**Mode:** {tournament.mode}\n**Abilities:** {tournament.abilities}",
                color=0x3498db
            )

            for i, match in enumerate(next_round_pairs, 1):
                if tournament.mode == "2v2":
                    team_a, team_b = match
                    team_a_str = f"{get_player_display_name(team_a[0])} & {get_player_display_name(team_a[1])}"
                    team_b_str = f"{get_player_display_name(team_b[0])} & {get_player_display_name(team_b[1])}"
                    embed.add_field(
                        name=f"⚔️ Match {i}",
                        value=f"**{team_a_str}** vs **{team_b_str}**\n🏆 Winner: *Waiting...*",
                        inline=False
                    )
                else:
                    a, b = match
                    player_a = get_player_display_name(a)
                    player_b = get_player_display_name(b)
                    embed.add_field(
                        name=f"⚔️ Match {i}",
                        value=f"**{player_a}** vs **{player_b}**\n🏆 Winner: *Waiting...*",
                        inline=False
                    )

            embed.set_footer(text="Use !winner @player to record match results")
            tournament.message = await ctx.send(embed=embed)

    # Update current tournament message to show the winner
    if tournament.message:
        try:
            current_embed = tournament.message.embeds[0]
            fields = current_embed.fields.copy()
            
            # Find and update the match field
            for i, field in enumerate(fields):
                if "Match" in field.name:
                    # Check if this match contains the winner
                    field_value = field.value
                    if tournament.mode == "2v2":
                        if any(get_player_display_name(p) in field_value for p in (member, tournament.teams.get(member.id, None) if member.id in tournament.teams else [])):
                            # Update the field to show winner
                            winner_team = f"{get_player_display_name(member)}"
                            if member.id in tournament.teams:
                                teammate = ctx.guild.get_member(tournament.teams[member.id])
                                winner_team += f" & {get_player_display_name(teammate)}"
                            
                            lines = field_value.split('\n')
                            lines[1] = f"🏆 Winner: **{winner_team}**"
                            
                            current_embed.set_field_at(i, name=field.name, value='\n'.join(lines), inline=field.inline)
                            break
                    else:
                        if get_player_display_name(member) in field_value:
                            lines = field_value.split('\n')
                            lines[1] = f"🏆 Winner: **{get_player_display_name(member)}**"
                            
                            current_embed.set_field_at(i, name=field.name, value='\n'.join(lines), inline=field.inline)
                            break
            
            await tournament.message.edit(embed=current_embed)
        except Exception as e:
            print(f"Error updating tournament message: {e}")

    await ctx.send(f"✅ {winner_name} wins their match!", delete_after=5)

class FakePlayer:
    def __init__(self, name, user_id):
        self.display_name = name
        self.name = name
        self.nick = name
        self.id = user_id
        self.mention = f"<@{user_id}>"
        
    def __str__(self):
        return self.mention

@bot.command()
async def fake(ctx, number: int = 1):
    try:
        await ctx.message.delete()
    except:
        pass

    if number < 1 or number > 16:
        return await ctx.send("❌ Number must be between 1 and 16.", delete_after=5)

    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament created yet.", delete_after=5)

    if tournament.active:
        return await ctx.send("❌ Tournament already started.", delete_after=5)

    available_spots = tournament.max_players - len(tournament.players)
    if number > available_spots:
        return await ctx.send(f"❌ Only {available_spots} spots available.", delete_after=5)

    # Create fake players as proper objects
    fake_players = []
    for i in range(number):
        fake_name = f"FakePlayer{tournament.fake_count}"
        fake_id = 761557952975420886 + tournament.fake_count  # Generate realistic Discord user ID
        fake_player = FakePlayer(fake_name, fake_id)
        fake_players.append(fake_player)
        tournament.players.append(fake_player)
        tournament.fake_count += 1

    fake_list = ", ".join([f.mention for f in fake_players])
    await ctx.send(f"🤖 Added {number} fake player{'s' if number > 1 else ''}: {fake_list}\nTotal players: {len(tournament.players)}/{tournament.max_players}", delete_after=10)

@bot.command()
async def code(ctx, code: str, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except:
        pass

    if not tournament.active:
        return await ctx.send("❌ No active tournament.", delete_after=5)

    # Get all players from current round who still need to play
    current_round = tournament.rounds[-1]
    round_players = set()  # Use set to prevent duplicates

    for match in current_round:
        if tournament.mode == "2v2":
            team_a, team_b = match
            # Add all real players from both teams in this match
            for player in [team_a[0], team_a[1], team_b[0], team_b[1]]:
                if hasattr(player, 'id') and not isinstance(player, FakePlayer):
                    round_players.add(player)
        else:
            a, b = match
            # Add both real players from this match
            for player in [a, b]:
                if hasattr(player, 'id') and not isinstance(player, FakePlayer):
                    round_players.add(player)

    if not round_players:
        return await ctx.send("❌ No real players found in current round.", delete_after=5)

    # Send code to all round players
    host_name = ctx.author.nick if ctx.author.nick else ctx.author.display_name
    code_message = f"🔐 **The room code is:** ```{code}```\n**Hosted by:** {host_name}"

    sent_count = 0
    failed_players = []

    for player in round_players:
        try:
            await player.send(code_message)
            sent_count += 1
        except discord.Forbidden:
            player_name = player.nick if player.nick else player.display_name
            failed_players.append(player_name)
        except Exception:
            player_name = player.nick if player.nick else player.display_name
            failed_players.append(player_name)

    if failed_players:
        await ctx.send(f"✅ Code sent to {sent_count} players via DM!\n❌ Failed to send to: {', '.join(failed_players)}", delete_after=10)
    else:
        await ctx.send(f"✅ Code sent to all {sent_count} round players via DM!", delete_after=5)

@bot.command()
async def cancel(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    tournament.__init__()
    await ctx.send("❌ Tournament cancelled.", delete_after=5)

async def main():
    """Main function to start the bot with keep_alive server"""
    await keep_alive()
    await bot.start(TOKEN)

# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ No Discord token found! Please add your bot token to the Secrets.")
        print("Go to the Secrets tool and add:")
        print("Key: TOKEN")
        print("Value: Your Discord bot token")
    else:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            