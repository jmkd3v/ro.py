"""

This file houses functions and classes that pertain to Roblox groups.

"""
import copy
from enum import Enum

import iso8601
import asyncio

from ro_py.wall import Wall
from ro_py.roles import Role
from ro_py.users import PartialUser
from ro_py.events import EventTypes
from typing import Tuple, Callable
from ro_py.utilities.errors import NotFound
from ro_py.utilities.pages import Pages, SortOrder

endpoint = "https://groups.roblox.com"


class Shout:
    """
    Represents a group shout.
    """
    def __init__(self, cso, shout_data):
        self.cso = cso
        self.data = shout_data
        self.body = shout_data["body"]
        # TODO: Make this a PartialUser
        self.poster = None


class JoinRequest:
    def __init__(self, cso, data, group):
        self.requests = cso.requests
        self.group = group
        self.requester = PartialUser(cso, data['requester']['userId'], data['requester']['username'])
        self.created = iso8601.parse_date(data['created'])

    async def accept(self):
        accept_req = await self.requests.post(
            url=endpoint + f"/v1/groups/{self.group.id}/join-requests/users/{self.requests.id}"
        )
        return accept_req.status_code == 200

    async def decline(self):
        accept_req = await self.requests.delete(
            url=endpoint + f"/v1/groups/{self.group.id}/join-requests/users/{self.requests.id}"
        )
        return accept_req.status_code == 200


class Actions(Enum):
    delete_post = "deletePost"
    remove_member = "removeMember"
    accept_join_request = "acceptJoinRequest"
    decline_join_request = "declineJoinRequest"
    post_shout = "postShout"
    change_rank = "changeRank"
    buy_ad = "buyAd"
    send_ally_request = "sendAllyRequest"
    create_enemy = "createEnemy"
    accept_ally_request = "acceptAllyRequest"
    decline_ally_request = "declineAllyRequest"
    delete_ally = "deleteAlly"
    add_group_place = "addGroupPlace"
    delete_group_place = "deleteGroupPlace"
    create_items = "createItems"
    configure_items = "configureItems"
    spend_group_funds = "spendGroupFunds"
    change_owner = "changeOwner"
    delete = "delete"
    adjust_currency_amounts = "adjustCurrencyAmounts"
    abandon = "abandon"
    claim = "claim"
    Rename = "rename"
    change_description = "changeDescription"
    create_group_asset = "createGroupAsset"
    upload_group_asset = "uploadGroupAsset"
    configure_group_asset = "configureGroupAsset"
    revert_group_asset = "revertGroupAsset"
    create_group_developer_product = "createGroupDeveloperProduct"
    configure_group_game = "configureGroupGame"
    lock = "lock"
    unlock = "unlock"
    create_game_pass = "createGamePass"
    create_badge = "createBadge"
    configure_badge = "configureBadge"
    save_place = "savePlace"
    publish_place = "publishPlace"
    invite_to_clan = "inviteToClan"
    kick_from_clan = "kickFromClan"
    cancel_clan_invite = "cancelClanInvite"
    buy_clan = "buyClan"


class Action:
    def __init__(self, cso, data, group):
        self.group = group
        self.actor = Member(cso, data['actor']['user']['userId'], data['actor']['user']['username'], group, Role(cso, group, data['actor']['role']))
        self.action = data['actionType']
        self.created = iso8601.parse_date(data['created'])
        self.data = data['description']


def action_handler(cso, data, args):
    actions = []
    for action in data:
        actions.append(Action(cso, action, args))
    return actions


def join_request_handler(cso, data, args):
    join_requests = []
    for request in data:
        join_requests.append(JoinRequest(cso, request, args))
    return join_requests


def member_handler(cso, data, args):
    members = []
    for member in data:
        members.append(member)
    return members


class Group:
    """
    Represents a group.
    """
    def __init__(self, cso, group_id):
        self.cso = cso
        """Client Shared Object"""
        self.requests = cso.requests
        "Requests object."
        self.id = group_id
        "Group ID."
        self.wall = Wall(self.cso, self)
        """Wall object."""
        self.name = None
        """Group name."""
        self.description = None
        """Group description."""
        self.owner = None
        """Group owner."""
        self.member_count = None
        """Group member count."""
        self.is_builders_club_only = None
        """True if the group is Builders Club (Premium) only. This seems to have been removed."""
        self.public_entry_allowed = None
        """Public entry allowed (private/public group)"""
        self.shout = None
        """Current group shout (Shout)"""
        self.events = Events(cso, self)
        """Events object."""
        self.is_locked = False
        """True if this is a locked group."""

    async def update(self):
        """
        Updates the group's information.
        """
        group_info_req = await self.requests.get(endpoint + f"/v1/groups/{self.id}")
        group_info = group_info_req.json()
        self.name = group_info["name"]
        self.description = group_info["description"]
        self.owner = await self.cso.client.get_user(group_info["owner"]["userId"])
        self.member_count = group_info["memberCount"]
        self.is_builders_club_only = group_info["isBuildersClubOnly"]
        self.public_entry_allowed = group_info["publicEntryAllowed"]
        if group_info.get('shout'):
            self.shout = Shout(self.cso, group_info['shout'])
        else:
            self.shout = None
        if "isLocked" in group_info:
            self.is_locked = group_info["isLocked"]

    async def update_shout(self, message):
        """
        Updates the shout of the group.

        Parameters
        ----------
        message : str
            Message that will overwrite the current shout of a group.

        Returns
        -------
        int
        """
        shout_req = await self.requests.patch(
            url=endpoint + f"/v1/groups/{self.id}/status",
            data={
                "message": message
            }
        )
        return shout_req.status_code == 200

    async def get_roles(self):
        """
        Gets all roles of the group.

        Returns
        -------
        list
        """
        role_req = await self.requests.get(
            url=endpoint + f"/v1/groups/{self.id}/roles"
        )
        roles = []
        for role in role_req.json()['roles']:
            roles.append(Role(self.cso, self, role))
        return roles

    async def get_member_by_id(self, roblox_id):
        # Get list of group user is in.
        member_req = await self.requests.get(
            url=endpoint + f"/v2/users/{roblox_id}/groups/roles"
        )
        data = member_req.json()

        # Find group in list.
        group_data = None
        for group in data['data']:
            if group['group']['id'] == self.id:
                group_data = group
                break

        # Check if user is in group.
        if not group_data:
            raise NotFound(f"The user {roblox_id} was not found in group {self.id}")

        # Create data to return.
        role = Role(self.cso, self, group_data['role'])
        member = Member(self.cso, roblox_id, "", self, role)
        return member

    async def get_member_by_username(self, name):
        user = await self.cso.client.get_user_by_username(name)
        member_req = await self.requests.get(
            url=endpoint + f"/v2/users/{user.id}/groups/roles"
        )
        data = member_req.json()

        # Find group in list.
        group_data = None
        for group in data['data']:
            if group['group']['id'] == self.id:
                group_data = group
                break

        # Check if user is in group.
        if not group_data:
            raise NotFound(f"The user {name} was not found in group {self.id}")

        # Create data to return.
        role = Role(self.cso, self, group_data['role'])
        member = Member(self.cso, user.id, user.name, self, role)
        return member

    async def get_join_requests(self, sort_order=SortOrder.Ascending, limit=100):
        pages = Pages(
            cso=self.cso,
            url=endpoint + f"/v1/groups/{self.id}/join-requests",
            sort_order=sort_order,
            limit=limit,
            handler=join_request_handler,
            handler_args=self
        )
        await pages.get_page()
        return pages

    async def get_members(self, sort_order=SortOrder.Ascending, limit=100):
        pages = Pages(
            cso=self.cso,
            url=endpoint + f"/v1/groups/{self.id}/users?limit=100&sortOrder=Desc",
            sort_order=sort_order,
            limit=limit,
            handler=member_handler,
            handler_args=self
        )

        await pages.get_page()
        return pages

    async def get_audit_logs(self, action_filter: Actions = None, sort_order=SortOrder.Ascending, limit=100):
        parameters = {}
        if action_filter:
            parameters['actionType'] = action_filter

        pages = Pages(
            cso=self.cso,
            url=endpoint + f"/v1/groups/{self.id}/audit-log",
            handler=action_handler,
            extra_parameters=parameters,
            handler_args=self,
            limit=limit,
            sort_order=sort_order
        )

        await pages.get_page()
        return pages


class PartialGroup:
    """
    Represents a group with less information.

    Different information will be present here in different circumstances.
    If it was generated as a game owner, it might only contain an ID and a name.
    If it was generated from, let's say, groups/v2/users/userid/groups/roles, it'll also contain a member count.
    """
    def __init__(self, cso, data):
        self.cso = cso
        self.requests = cso.requests
        self.id = data["id"]
        self.name = data["name"]
        self.member_count = None
        if "memberCount" in data:
            self.member_count = data["memberCount"]

    async def expand(self):
        return self.cso.client.get_group(self.id)


class Member(PartialUser):
    """
    Represents a user in a group.

    Parameters
    ----------
    cso : ro_py.utilities.requests.Requests
            Requests object to use for API requests.
    roblox_id : int
            The id of a user.
    name : str
            The name of the user.
    group : ro_py.groups.Group
            The group the user is in.
    role : ro_py.roles.Role
            The role the user has is the group.
    """
    def __init__(self, cso, roblox_id, name, group, role):
        super().__init__(cso, roblox_id, name)
        self.role = role
        self.group = group

    async def update_role(self):
        """
        Updates the role information of the user.

        Returns
        -------
        ro_py.roles.Role
        """
        member_req = await self.requests.get(
            url=endpoint + f"/v2/users/{self.id}/groups/roles"
        )
        data = member_req.json()
        for role in data['data']:
            if role['group']['id'] == self.group.id:
                self.role = Role(self.cso, self.group, role['role'])
                break
        return self.role

    async def change_rank(self, num) -> Tuple[Role, Role]:
        """
        Changes the users rank specified by a number.
        If num is 1 the users role will go up by 1.
        If num is -1 the users role will go down by 1.

        Parameters
        ----------
        num : int
                How much to change the rank by.
        """
        await self.update_role()
        roles = await self.group.get_roles()
        old_role = copy.copy(self.role)
        role_counter = -1
        for group_role in roles:
            role_counter += 1
            if group_role.rank == self.role.id:
                break
        if not roles:
            raise NotFound(f"User {self.id} is not in group {self.group.id}")
        await self.setrank(roles[role_counter + num].id)
        self.role = roles[role_counter + num].id
        return old_role, roles[role_counter + num]

    async def promote(self):
        """
        Promotes the user.

        Returns
        -------
        int
        """
        return await self.change_rank(1)

    async def demote(self):
        """
        Demotes the user.

        Returns
        -------
        int
        """
        return await self.change_rank(-1)

    async def setrank(self, rank):
        """
        Sets the users role to specified role using rank id.

        Parameters
        ----------
        rank : int
                Rank id

        Returns
        -------
        bool
        """
        rank_request = await self.requests.patch(
            url=endpoint + f"/v1/groups/{self.group.id}/users/{self.id}",
            data={
                "roleId": rank
            }
        )
        return rank_request.status_code == 200

    async def setrole(self, role_num):
        """
         Sets the users role to specified role using role number (1-255).

         Parameters
         ----------
         role_num : int
                Role number (1-255)

         Returns
         -------
         bool
         """
        roles = await self.group.get_roles()
        rank_role = None
        for role in roles:
            if role.rank == role_num:
                rank_role = role
                break
        if not rank_role:
            raise NotFound(f"Role {role_num} not found")
        return await self.setrank(rank_role.id)

    async def exile(self):
        exile_req = await self.requests.delete(
            url=endpoint + f"/v1/groups/{self.group.id}/users/{self.id}"
        )
        return exile_req.status_code == 200


class Events:
    def __init__(self, cso, group):
        self.cso = cso
        self.group = group

    def bind(self, func: Callable, event: EventTypes, delay: int = 15):
        """
        Binds a function to an event.

        Parameters
        ----------
        func : function
                Function that will be bound to the event.
        event : ro_py.events.EventTypes
                Event that will be bound to the function.
        delay : int
                How many seconds between each poll.
        """
        if event == EventTypes.on_join_request:
            return asyncio.create_task(self.on_join_request(func, delay))
        if event == EventTypes.on_wall_post:
            return asyncio.create_task(self.on_wall_post(func, delay))
        if event == EventTypes.on_group_change:
            return asyncio.create_task(self.on_group_change(func, delay))
        if event == EventTypes.on_audit_log:
            return asyncio.create_task(self.on_audit_log(func, delay))

    async def on_join_request(self, func: Callable, delay: int):
        current_group_reqs = await self.group.get_join_requests()
        old_req = current_group_reqs.data.requester.id
        while True:
            await asyncio.sleep(delay)
            current_group_reqs = await self.group.get_join_requests()
            current_group_reqs = current_group_reqs.data
            if current_group_reqs[0].requester.id != old_req:
                new_reqs = []
                for request in current_group_reqs:
                    if request.requester.id != old_req:
                        new_reqs.append(request)
                old_req = current_group_reqs[0].requester.id
                for new_req in new_reqs:
                    asyncio.create_task(func(new_req))

    async def on_wall_post(self, func: Callable, delay: int):
        current_wall_posts = await self.group.wall.get_posts(sort_order=SortOrder.Descending)
        newest_wall_post = current_wall_posts.data[0].id
        while True:
            await asyncio.sleep(delay)
            current_wall_posts = await self.group.wall.get_posts(sort_order=SortOrder.Descending)
            current_wall_posts = current_wall_posts.data
            post = current_wall_posts[0]
            if post.id != newest_wall_post:
                new_posts = []
                for post in current_wall_posts:
                    if post.id == newest_wall_post:
                        break
                    new_posts.append(post)
                newest_wall_post = current_wall_posts[0].id
                for new_post in new_posts:
                    asyncio.create_task(func(new_post))

    async def on_group_change(self, func: Callable, delay: int):
        await self.group.update()
        current_group = copy.copy(self.group)
        while True:
            await asyncio.sleep(delay)
            await self.group.update()
            has_changed = False
            for attr, value in current_group.__dict__.items():
                if getattr(self.group, attr) != value:
                    has_changed = True
            if has_changed:
                asyncio.create_task(func(current_group, self.group))

    """
    async def on_audit_log(self, func: Callable, delay: int):
        audit_log = await self.group.get_audit_logs()
        audit_log = audit_log.data[0]
        while True:
            await asyncio.sleep(delay)
            new_audit = await self.group.get_audit_logs()
            new_audits = []
            for audit in new_audit.data:
                if audit.created == audit_log.created:
                    print(audit.created, audit_log.created, audit.created == audit_log.created)
                    break
                else:
                    print(audit.created, audit_log.created)
                    new_audits.append(audit)
            if len(new_audits) > 0:
                audit_log = new_audit.data[0]
                for new in new_audits:
                    asyncio.create_task(func(new))
    """
