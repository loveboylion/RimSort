import json
import logging
from math import ceil
from requests.exceptions import HTTPError
import sys
from time import time
from typing import Any, Dict, List, Optional, Tuple, Union

from window.runner_panel import RunnerPanel

from steam.webapi import WebAPI

logger = logging.getLogger(__name__)
# Uncomment this if you want to see the full urllib3 request
# THIS CONTAINS THE STEAM API KEY
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


class AppIDQuery:
    """
    Create AppIDQuery object to initialize the scraped data from Workshop
    """

    def __init__(self, apikey: str, appid: int):
        self.all_mods_metadata = {}
        self.api = WebAPI(apikey, format="json", https=True)
        self.apikey = apikey
        self.appid = appid
        self.next_cursor = "*"
        self.pagenum = 1
        self.pages = 1
        self.publishedfileids = []
        self.query = True
        self.total = 0
        logger.info(
            f"AppIDQuery initializing... Compiling list of all Workshop mod PublishedFileIDs for {self.appid}..."
        )
        while self.query:
            if self.pagenum > self.pages:
                self.query = False
                break
            self.next_cursor = self.IPublishedFileService_QueryFiles(self.next_cursor)

    def _all_mods_metadata_by_appid(self, life: int) -> Dict[Any, Any]:
        """
        Utilizes DynamicQuery object to return an complete query of an AppID's
        Steam Workshop mod catalogue's metadata from Steam WebAPI

        :param life: The lifespan of the Query in terms of the seconds added to the time of
        database generation. This adds an 'expiry' to the data being cached.
        """
        all_publishings_metadata_query = DynamicQuery(self.apikey, self.appid, 1800)
        db = {}
        db["version"] = all_publishings_metadata_query.expiry
        db["database"] = {}
        logger.info(
            f"Populating {str(len(self.publishedfileids))} empty keys into initial database for "
            + f"{self.appid}."
        )
        for publishedfileid in self.publishedfileids:
            db["database"][publishedfileid] = {}
        # Begin initial query
        logger.info(
            f"Populated {str(len(self.publishedfileids))} PublishedFileIds into database"
        )
        logger.info("Beginning initial query...")
        (  # Initial population of steamName, url, and empty dependencies {}
            db,
            missing_children,
        ) = all_publishings_metadata_query.IPublishedFileService_GetDetails(
            db, True, self.publishedfileids
        )
        # Begin secondary query
        logger.info(
            f"Initial query completed. Initiating second pass to populate full dependency data for {str(len(self.publishedfileids))} PublishedFileIds"
        )
        (  # Secondary pass to piece together the dependency data
            db,
            missing_children,
        ) = all_publishings_metadata_query.IPublishedFileService_GetDetails(
            db, False, self.publishedfileids
        )
        logger.info(
            f"A total of {str(len(missing_children))} missing children were returned with this query."
        )
        logger.info(
            "This indicates that some of the published mods queried have children listed who's PublishedFileIds are no longer searchable in the Steam Workshop catalogue."
        )
        logger.info(
            "This message is for informational purposes only, so that you understand why these are missing from your query."
        )
        total = len(db["database"])
        logger.info(f"Returning Steam Workshop metadata with {total} PublishedFileIds")
        return db

    def IPublishedFileService_QueryFiles(self, cursor: str) -> str:
        """
        Utility to crawl the entirety of Rimworld's Steam Workshop catalogue, compile,
        and populate a list of all PublishedFileIDs

        Given a string cursor, return a string next_cursor from Steam WebAPI, from the
        data being parsed from the loop of each page - API has 100 item limit per page

        https://steamapi.xpaw.me/#IPublishedFileService/QueryFiles
        https://partner.steamgames.com/doc/webapi/IPublishedFileService#QueryFiles
        https://steamwebapi.azurewebsites.net (Ctrl + F search: "IPublishedFileService/QueryFiles")

        :param str: IN string containing the variable that corresponds to the
        `cursor` parameter being passed to the CURRENT WebAPI.call() query

        :return: OUT string containing the variable that corresponds to the
        `cursor` parameter being returned to the FOLLOWING loop in our series of
        WebAPI.call() results that are being are parsing
        """

        result = self.api.call(
            method_path="IPublishedFileService.QueryFiles",
            key=self.apikey,
            query_type=1,
            page=1,
            cursor=cursor,
            numperpage=50000,
            creator_appid=self.appid,
            appid=self.appid,
            requiredtags=None,
            excludedtags=None,
            match_all_tags=False,
            required_flags=None,
            omitted_flags=None,
            search_text="",
            filetype=0,
            child_publishedfileid=None,
            days=None,
            include_recent_votes_only=False,
            required_kv_tags=None,
            taggroups=None,
            date_range_created=None,
            date_range_updated=None,
            excluded_content_descriptors=None,
            totalonly=False,
            ids_only=True,
            return_vote_data=False,
            return_tags=False,
            return_kv_tags=False,
            return_previews=False,
            return_children=True,
            return_short_description=False,
            return_for_sale_data=False,
            return_playtime_stats=False,
            return_details=False,
            strip_description_bbcode=False,
        )
        # Print total mods found we need to iter through paginations to get info for
        if (
            self.pagenum and self.total == 0
        ):  # If True, this is initial loop; we properly set them in initial loop
            if result["response"]["total"]:
                self.pagenum = 1
                self.total = result["response"]["total"]
                self.pages = ceil(
                    self.total / len(result["response"]["publishedfiledetails"])
                )
                logger.info(f"Total mod items to parse: {str(self.total)}")
        logger.info(
            f"IPublishedFileService.QueryFiles page [{str(self.pagenum)}"
            + f"/{str(self.pages)}]"
        )
        ids_from_page = []
        for item in result["response"]["publishedfiledetails"]:
            self.publishedfileids.append(item["publishedfileid"])
            ids_from_page.append(item["publishedfileid"])
        self.pagenum += 1
        return result["response"]["next_cursor"]


class DynamicQuery:
    """
    Create DynamicQuery object to initialize the scraped data from Workshop

    :param apikey: Steam API key to be used for query
    :param appid: The AppID associated with the game you are looking up info for
    :param life: The lifespan of the Query in terms of the seconds added to the time of
    database generation. This adds an 'expiry' to the data being cached.
    """

    def __init__(self, apikey: str, appid: int, life: int):
        self.api = WebAPI(apikey, format="json", https=True)
        self.apikey = apikey
        self.appid = appid
        self.expiry = self.__expires(life)
        self.workshop_json_data = {}
        logger.info(f"DynamicQuery initialized...")

    def __chunks(self, _list: list, limit: int):
        """
        Split list into chunks no larger than the configured limit

        :param _list: a list to break into chunks
        :param limit: maximum size of the returned list
        """
        for i in range(0, len(_list), limit):
            yield _list[i : i + limit]

    def __expires(self, life: int) -> int:
        return int(time() + life)  # current seconds since epoch + 30 minutes

    def cache_parsable_db_data(self, mods: Dict[str, Any]) -> Dict[Any, Any]:
        """
        Builds a database using a chunked WebAPI query of all available PublishedFileIds
        that are pulled from local mod metadata.

        :param mods: a Dict equivalent to 'all_mods' or mod_list.get_list_items_by_dict()
        in which contains possible Steam mods to lookup metadata for
        :return: a RimPy Mod Manager db_data["database"] equivalent, stitched together from
        local metadata & the Workshop metadata result from a live WebAPI query of those mods
        """
        authors = ""
        gameVersions = []
        pfid = ""
        pid = ""
        name = ""
        local_metadata = {}
        local_metadata["database"] = {}
        publishedfileids = []
        for v in mods.values():
            if v.get("publishedfileid"):
                pfid = v["publishedfileid"]
                url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={pfid}"
                local_metadata["database"][pfid] = {}
                local_metadata["database"][pfid]["url"] = url
                publishedfileids.append(pfid)
                if v.get("packageId"):
                    pid = v["packageId"]
                    local_metadata["database"][pfid]["packageId"] = pid
                if v.get("name"):
                    name = v["name"]
                    local_metadata["database"][pfid]["name"] = name
                if v.get("author"):
                    authors = v["author"]
                    local_metadata["database"][pfid]["authors"] = authors
                if v["supportedVersions"].get("li"):
                    gameVersions = v["supportedVersions"]["li"]
                    local_metadata["database"][pfid]["gameVersions"] = gameVersions
        logger.info(f"DynamicQuery initializing for {len(publishedfileids)} mods")
        query = {}
        query["version"] = self.expiry
        query["database"] = local_metadata["database"]
        querying = True
        while querying:  # Begin initial query
            (  # Returns WHAT we can get remotely, FROM what we have locally
                query,
                missing_children,
            ) = self.IPublishedFileService_GetDetails(query, False, publishedfileids)
            if (
                len(missing_children) > 0
            ):  # If we have missing data for any dependency...
                logger.info(
                    f"Retrieving dependency information for the following missing children: {missing_children}"
                )
                # Extend publishedfileids with the missing_children PublishedFileIds for final query
                publishedfileids.extend(missing_children)
                # Launch a separate query from the initial, to recursively append
                # any of the missing_children's metadata to the query["database"].
                #
                # This will ensure that we get ALL dependency data that is possible,
                # even if we do not have the dependenc{y, ies}. It's not perfect,
                # because it will always cause one additional full query to ensure that
                # the query["database"] is complete with missing_children metadata.
                #
                # It is the only way to paint the full picture without already
                # possessing the mod's metadata for the initial query.
                (query, missing_children,) = self.IPublishedFileService_GetDetails(
                    query, False, missing_children
                )
            else:  # Stop querying once we have 0 missing_children
                missing_children = []
                querying = False
        total = len(query["database"])
        logger.info(f"Returning Steam Workshop metadata for {total} PublishedFileIds")
        return query

    def IPublishedFileService_GetDetails(
        self, json_to_update: Dict[Any, Any], override: bool, publishedfileids: list
    ) -> Tuple[Dict[Any, Any], list]:
        """
        Given a list of PublishedFileIds, return a dict of json data queried
        from Steam WebAPI, containing data to be parsed during db update.

        https://steamapi.xpaw.me/#IPublishedFileService/GetDetails
        https://steamwebapi.azurewebsites.net (Ctrl + F search: "IPublishedFileService/GetUserFiles")

        :param json_to_update: a Dict of json data, containing a query to update in
        RimPy db_data["database"] format, or the skeleton of one from local_metadata
        :param publishedfileids: a list of PublishedFileIds to query Steam Workshop mod metadata for
        :return: Tuple containing the updated json data from PublishedFileIds query, as well as
        a list of any missing children's PublishedFileIds to consider for additional queries
        """
        missing_children = []
        result = json_to_update
        for batch in self.__chunks(
            publishedfileids, 215
        ):  # Batch limit appears to be 215 PublishedFileIds at a time - this appears to be a WebAPI limitation
            logger.info(f"Retrieving metadata for {len(batch)} mods")
            response = self.api.call(
                method_path="IPublishedFileService.GetDetails",
                key=self.apikey,
                publishedfileids=batch,
                includetags=False,
                includeadditionalpreviews=False,
                includechildren=True,
                includekvtags=True,
                includevotes=False,
                short_description=False,
                includeforsaledata=False,
                includemetadata=True,
                return_playtime_stats=0,
                appid=self.appid,
                strip_description_bbcode=False,
                includereactions=False,
            )
            for metadata in response["response"]["publishedfiledetails"]:
                publishedfileid = metadata[
                    "publishedfileid"
                ]  # Set the PublishedFileId to that of the metadata we are parsing
                if (
                    override
                ):  # Override assumes we have ALL PublishedFileIDs available. Does not get dependency data.
                    if metadata["result"] != 1:  # If the mod is no longer published
                        logger.warning(
                            f"Tried to parse metadata for a mod that is deleted/private/removed/unposted: {publishedfileid}"
                        )
                        result["database"][
                            publishedfileid
                        ][  # Reflect the mod's status in it's attributes
                            "steamName"
                        ] = "Missing mod: deleted/private/removed/unposted"
                        result["database"][publishedfileid]["unpublished"] = True
                        continue
                    result["database"][publishedfileid][
                        "url"
                    ] = f"https://steamcommunity.com/sharedfiles/filedetails/?id={publishedfileid}"
                    result["database"][publishedfileid]["steamName"] = metadata["title"]
                    result["database"][publishedfileid]["dependencies"] = {}
                elif not result["database"].get(
                    publishedfileid
                ):  # If we don't already have a ["database"] entry for this pfid
                    result["database"][publishedfileid] = {}  # Add in skeleton data
                    result["database"][publishedfileid][
                        "url"
                    ] = f"https://steamcommunity.com/sharedfiles/filedetails/?id={publishedfileid}"
                    result["database"][publishedfileid][
                        "steamName"
                    ] = "Steam metadata unavailable"
                    result["database"][publishedfileid]["missing"] = True
                    if metadata["result"] != 1:  # If the mod is no longer published
                        logger.warning(
                            f"Tried to parse metadata for a mod that is deleted/private/removed/unposted: {publishedfileid}"
                        )
                        result["database"][
                            publishedfileid
                        ][  # Reflect the mod's status in it's attributes
                            "steamName"
                        ] = "Missing mod: deleted/private/removed/unposted"
                        result["database"][publishedfileid]["unpublished"] = True
                else:
                    if result["database"][publishedfileid].get(
                        "unpublished"
                    ):  # If mod is unpublished, it has no metadata
                        continue
                    result["database"][publishedfileid]["steamName"] = metadata["title"]
                    result["database"][publishedfileid]["dependencies"] = {}
                    if metadata.get("children"):
                        for children in metadata[
                            "children"
                        ]:  # Check if children present in database
                            child_pfid = children["publishedfileid"]
                            if result["database"].get(
                                child_pfid
                            ):  # If we have data for this child already cached, populate it
                                if result["database"][child_pfid].get(
                                    "name"
                                ):  # Use local name over Steam name if possible
                                    child_name = result["database"][child_pfid]["name"]
                                elif result["database"][child_pfid].get("steamName"):
                                    child_name = result["database"][child_pfid][
                                        "steamName"
                                    ]
                                else:
                                    logger.warning(
                                        f"Unable to find name for child {child_pfid}"
                                    )
                                if result["database"][child_pfid].get("url"):
                                    child_url = result["database"][child_pfid]["url"]
                                else:
                                    logger.warning(
                                        f"Unable to find url for child {child_pfid}"
                                    )
                                result["database"][publishedfileid]["dependencies"][
                                    child_pfid
                                ] = [child_name, child_url]
                            else:  # Child was not found in database, track it's pfid for later
                                if child_pfid not in missing_children:
                                    logger.warning(
                                        f"Could not find pfid {child_pfid} in database. Adding child to missing_children..."
                                    )
                                    missing_children.append(child_pfid)

        return result, missing_children


if __name__ == "__main__":
    sys.exit()