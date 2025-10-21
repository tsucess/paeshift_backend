
from django.shortcuts import render

import json
#from oauth2client.client import SignedJwtAssertionCredentials

from django import template
from chatapp.decorators import allowed_user
from Projects.models import ProjectStatus, Task, ProjectProfile
from Finance.models import UserIncome, Expense, UserPreference
from chatapp.models import leads as Leads, deals as Deals, visited
from invoice.models import AddCustomer
from proposal.models import Proposal, ProposalStatus
from .models import integrations as Integrations
from campaigns.models import MailStatus
import datetime
from campaigns.models import MailStatus
register = template.Library()


def data_report(request):
    metrics= ['users', 'newUsers', 'percentNewSessions', '1dayUsers', '7dayUsers', '14dayUsers', '28dayUsers', '30dayUsers', 'sessions', 'bounces', 'bounceRate', 'sessionDuration', 'avgSessionDuration', 'organicSearches', 'impressions', 'adClicks', 'adCost', 'CPM', 'CPC', 'CTR', 'costPerTransaction', 'costPerGoalConversion', 'costPerConversion', 'RPC', 'ROAS', 'goal1Starts', 'goal2Starts', 'goal3Starts', 'goal4Starts', 'goal5Starts', 'goal6Starts', 'goal7Starts', 'goal8Starts', 'goal9Starts', 'goal10Starts', 'goal11Starts', 'goal12Starts', 'goal13Starts', 'goal14Starts', 'goal15Starts', 'goal16Starts', 'goal17Starts', 'goal18Starts', 'goal19Starts', 'goal20Starts', 'goalStartsAll', 'goal1Completions', 'goal2Completions', 'goal3Completions', 'goal4Completions', 'goal5Completions', 'goal6Completions', 'goal7Completions', 'goal8Completions', 'goal9Completions', 'goal10Completions', 'goal11Completions', 'goal12Completions', 'goal13Completions', 'goal14Completions', 'goal15Completions', 'goal16Completions', 'goal17Completions', 'goal18Completions', 'goal19Completions', 'goal20Completions', 'goalCompletionsAll', 'goal1Value', 'goal2Value', 'goal3Value', 'goal4Value', 'goal5Value', 'goal6Value', 'goal7Value', 'goal8Value', 'goal9Value', 'goal10Value', 'goal11Value', 'goal12Value', 'goal13Value', 'goal14Value', 'goal15Value', 'goal16Value', 'goal17Value', 'goal18Value', 'goal19Value', 'goal20Value', 'goalValueAll', 'goalValuePerSession', 'goal1ConversionRate', 'goal2ConversionRate', 'goal3ConversionRate', 'goal4ConversionRate', 'goal5ConversionRate', 'goal6ConversionRate', 'goal7ConversionRate', 'goal8ConversionRate', 'goal9ConversionRate', 'goal10ConversionRate', 'goal11ConversionRate', 'goal12ConversionRate', 'goal13ConversionRate', 'goal14ConversionRate', 'goal15ConversionRate', 'goal16ConversionRate', 'goal17ConversionRate', 'goal18ConversionRate', 'goal19ConversionRate', 'goal20ConversionRate', 'goalConversionRateAll', 'goal1Abandons', 'goal2Abandons', 'goal3Abandons', 'goal4Abandons', 'goal5Abandons', 'goal6Abandons', 'goal7Abandons', 'goal8Abandons', 'goal9Abandons', 'goal10Abandons', 'goal11Abandons', 'goal12Abandons', 'goal13Abandons', 'goal14Abandons', 'goal15Abandons', 'goal16Abandons', 'goal17Abandons', 'goal18Abandons', 'goal19Abandons', 'goal20Abandons', 'goalAbandonsAll', 'goal1AbandonRate', 'goal2AbandonRate', 'goal3AbandonRate', 'goal4AbandonRate', 'goal5AbandonRate', 'goal6AbandonRate', 'goal7AbandonRate', 'goal8AbandonRate', 'goal9AbandonRate', 'goal10AbandonRate', 'goal11AbandonRate', 'goal12AbandonRate', 'goal13AbandonRate', 'goal14AbandonRate', 'goal15AbandonRate', 'goal16AbandonRate', 'goal17AbandonRate', 'goal18AbandonRate', 'goal19AbandonRate', 'goal20AbandonRate', 'goalAbandonRateAll', 'pageValue', 'entrances', 'entranceRate', 'pageviews', 'pageviewsPerSession', 'contentGroupUniqueViews1', 'contentGroupUniqueViews2', 'contentGroupUniqueViews3', 'contentGroupUniqueViews4', 'contentGroupUniqueViews5', 'uniquePageviews', 'timeOnPage', 'avgTimeOnPage', 'exits', 'exitRate', 'searchResultViews', 'searchUniques', 'avgSearchResultViews', 'searchSessions', 'percentSessionsWithSearch', 'searchDepth', 'avgSearchDepth', 'searchRefinements', 'percentSearchRefinements', 'searchDuration', 'avgSearchDuration', 'searchExits', 'searchExitRate', 'searchGoal1ConversionRate', 'searchGoal2ConversionRate', 'searchGoal3ConversionRate', 'searchGoal4ConversionRate', 'searchGoal5ConversionRate', 'searchGoal6ConversionRate', 'searchGoal7ConversionRate', 'searchGoal8ConversionRate', 'searchGoal9ConversionRate', 'searchGoal10ConversionRate', 'searchGoal11ConversionRate', 'searchGoal12ConversionRate', 'searchGoal13ConversionRate', 'searchGoal14ConversionRate', 'searchGoal15ConversionRate', 'searchGoal16ConversionRate', 'searchGoal17ConversionRate', 'searchGoal18ConversionRate', 'searchGoal19ConversionRate', 'searchGoal20ConversionRate', 'searchGoalConversionRateAll', 'goalValueAllPerSearch', 'pageLoadTime', 'pageLoadSample', 'avgPageLoadTime', 'domainLookupTime', 'avgDomainLookupTime', 'pageDownloadTime', 'avgPageDownloadTime', 'redirectionTime', 'avgRedirectionTime', 'serverConnectionTime', 'avgServerConnectionTime', 'serverResponseTime', 'avgServerResponseTime', 'speedMetricsSample', 'domInteractiveTime', 'avgDomInteractiveTime', 'domContentLoadedTime', 'avgDomContentLoadedTime', 'domLatencyMetricsSample', 'screenviews', 'uniqueScreenviews', 'screenviewsPerSession', 'timeOnScreen', 'avgScreenviewDuration', 'totalEvents', 'uniqueDimensionCombinations', 'uniqueEvents', 'eventValue', 'avgEventValue', 'sessionsWithEvent', 'eventsPerSessionWithEvent', 'transactions', 'transactionsPerSession', 'transactionRevenue', 'revenuePerTransaction', 'transactionRevenuePerSession', 'transactionShipping', 'transactionTax', 'totalValue', 'itemQuantity', 'uniquePurchases', 'revenuePerItem', 'itemRevenue', 'itemsPerPurchase', 'localTransactionRevenue', 'localTransactionShipping', 'localTransactionTax', 'localItemRevenue', 'socialInteractions', 'uniqueSocialInteractions', 'socialInteractionsPerSession', 'userTimingValue', 'userTimingSample', 'avgUserTimingValue', 'exceptions', 'exceptionsPerScreenview', 'fatalExceptions', 'fatalExceptionsPerScreenview', 'metric1', 'metric2', 'metric3', 'metric4', 'metric5', 'metric6', 'metric7', 'metric8', 'metric9', 'metric10', 'metric11', 'metric12', 'metric13', 'metric14', 'metric15', 'metric16', 'metric17', 'metric18', 'metric19', 'metric20', 'dcmFloodlightQuantity', 'dcmFloodlightRevenue', 'adsenseRevenue', 'adsenseAdUnitsViewed', 'adsenseAdsViewed', 'adsenseAdsClicks', 'adsensePageImpressions', 'adsenseCTR', 'adsenseECPM', 'adsenseExits', 'adsenseViewableImpressionPercent', 'adsenseCoverage', 'totalPublisherImpressions', 'totalPublisherCoverage', 'totalPublisherMonetizedPageviews', 'totalPublisherImpressionsPerSession', 'totalPublisherViewableImpressionsPercent', 'totalPublisherClicks', 'totalPublisherCTR', 'totalPublisherRevenue', 'totalPublisherRevenuePer1000Sessions', 'totalPublisherECPM', 'adxImpressions', 'adxCoverage', 'adxMonetizedPageviews', 'adxImpressionsPerSession', 'adxViewableImpressionsPercent', 'adxClicks', 'adxCTR', 'adxRevenue', 'adxRevenuePer1000Sessions', 'adxECPM', 'dfpImpressions', 'dfpCoverage', 'dfpMonetizedPageviews', 'dfpImpressionsPerSession', 'dfpViewableImpressionsPercent', 'dfpClicks', 'dfpCTR', 'dfpRevenue', 'dfpRevenuePer1000Sessions', 'dfpECPM', 'backfillImpressions', 'backfillCoverage', 'backfillMonetizedPageviews', 'backfillImpressionsPerSession', 'backfillViewableImpressionsPercent', 'backfillClicks', 'backfillCTR', 'backfillRevenue', 'backfillRevenuePer1000Sessions', 'backfillECPM', 'buyToDetailRate', 'calcMetric_<NAME>', 'cartToDetailRate', 'cohortActiveUsers', 'cohortAppviewsPerUser', 'cohortAppviewsPerUserWithLifetimeCriteria', 'cohortGoalCompletionsPerUser', 'cohortGoalCompletionsPerUserWithLifetimeCriteria', 'cohortPageviewsPerUser', 'cohortPageviewsPerUserWithLifetimeCriteria', 'cohortRetentionRate', 'cohortRevenuePerUser', 'cohortRevenuePerUserWithLifetimeCriteria', 'cohortSessionDurationPerUser', 'cohortSessionDurationPerUserWithLifetimeCriteria', 'cohortSessionsPerUser', 'cohortSessionsPerUserWithLifetimeCriteria', 'cohortTotalUsers', 'cohortTotalUsersWithLifetimeCriteria', 'dbmCPA', 'dbmCPC', 'dbmCPM', 'dbmCTR', 'dbmClicks', 'dbmConversions', 'dbmCost', 'dbmImpressions', 'dbmROAS', 'dcmCPC', 'dcmCTR', 'dcmClicks', 'dcmCost', 'dcmImpressions', 'dcmROAS', 'dcmRPC', 'dsCPC', 'dsCTR', 'dsClicks', 'dsCost', 'dsImpressions', 'dsProfit', 'dsReturnOnAdSpend', 'dsRevenuePerClick', 'hits', 'internalPromotionCTR', 'internalPromotionClicks', 'internalPromotionViews', 'localProductRefundAmount', 'localRefundAmount', 'productAddsToCart', 'productCheckouts', 'productDetailViews', 'productListCTR', 'productListClicks', 'productListViews', 'productRefundAmount', 'productRefunds', 'productRemovesFromCart', 'productRevenuePerPurchase', 'quantityAddedToCart', 'quantityCheckedOut', 'quantityRefunded', 'quantityRemovedFromCart', 'refundAmount', 'revenuePerUser', 'sessionsPerUser', 'totalRefunds', 'transactionsPerUser']
    dimensions = ['userType', 'sessionCount', 'daysSinceLastSession', 'userDefinedValue', 'userBucket', 'sessionDurationBucket', 'referralPath', 'fullReferrer', 'campaign', 'source', 'medium', 'sourceMedium', 'keyword', 'adContent', 'socialNetwork', 'hasSocialSourceReferral', 'adGroup', 'adSlot', 'adDistributionNetwork', 'adMatchType', 'adKeywordMatchType', 'adMatchedQuery', 'adPlacementDomain', 'adPlacementUrl', 'adFormat', 'adTargetingType', 'adTargetingOption', 'adDisplayUrl', 'adDestinationUrl', 'adwordsCustomerID', 'adwordsCampaignID', 'adwordsAdGroupID', 'adwordsCreativeID', 'adwordsCriteriaID', 'adQueryWordCount', 'goalCompletionLocation', 'goalPreviousStep1', 'goalPreviousStep2', 'goalPreviousStep3', 'browser', 'browserVersion', 'operatingSystem', 'operatingSystemVersion', 'mobileDeviceBranding', 'mobileDeviceModel', 'mobileInputSelector', 'mobileDeviceInfo', 'mobileDeviceMarketingName', 'deviceCategory', 'continent', 'subContinent', 'country', 'region', 'metro', 'city', 'latitude', 'longitude', 'networkDomain', 'networkLocation', 'flashVersion', 'javaEnabled', 'language', 'screenColors', 'sourcePropertyDisplayName', 'sourcePropertyTrackingId', 'screenResolution', 'hostname', 'pagePath', 'pagePathLevel1', 'pagePathLevel2', 'pagePathLevel3', 'pagePathLevel4', 'pageTitle', 'landingPagePath', 'secondPagePath', 'exitPagePath', 'previousPagePath', 'pageDepth', 'searchUsed', 'searchKeyword', 'searchKeywordRefinement', 'searchCategory', 'searchStartPage', 'searchDestinationPage', 'searchAfterDestinationPage', 'appInstallerId', 'appVersion', 'appName', 'appId', 'screenName', 'screenDepth', 'landingScreenName', 'exitScreenName', 'eventCategory', 'eventAction', 'eventLabel', 'transactionId', 'affiliation', 'sessionsToTransaction', 'daysToTransaction', 'productSku', 'productName', 'productCategory', 'currencyCode', 'socialInteractionNetwork', 'socialInteractionAction', 'socialInteractionNetworkAction', 'socialInteractionTarget', 'socialEngagementType', 'userTimingCategory', 'userTimingLabel', 'userTimingVariable', 'exceptionDescription', 'experimentId', 'experimentVariant', 'dimension1', 'dimension2', 'dimension3', 'dimension4', 'dimension5', 'dimension6', 'dimension7', 'dimension8', 'dimension9', 'dimension10', 'dimension11', 'dimension12', 'dimension13', 'dimension14', 'dimension15', 'dimension16', 'dimension17', 'dimension18', 'dimension19', 'dimension20', 'customVarName1', 'customVarName2', 'customVarName3', 'customVarName4', 'customVarName5', 'customVarValue1', 'customVarValue2', 'customVarValue3', 'customVarValue4', 'customVarValue5', 'date', 'year', 'month', 'week', 'day', 'hour', 'minute', 'nthMonth', 'nthWeek', 'nthDay', 'nthMinute', 'dayOfWeek', 'dayOfWeekName', 'dateHour', 'dateHourMinute', 'yearMonth', 'yearWeek', 'isoWeek', 'isoYear', 'isoYearIsoWeek', 'dcmClickAd', 'dcmClickAdId', 'dcmClickAdType', 'dcmClickAdTypeId', 'dcmClickAdvertiser', 'dcmClickAdvertiserId', 'dcmClickCampaign', 'dcmClickCampaignId', 'dcmClickCreativeId', 'dcmClickCreative', 'dcmClickRenderingId', 'dcmClickCreativeType', 'dcmClickCreativeTypeId', 'dcmClickCreativeVersion', 'dcmClickSite', 'dcmClickSiteId', 'dcmClickSitePlacement', 'dcmClickSitePlacementId', 'dcmClickSpotId', 'dcmFloodlightActivity', 'dcmFloodlightActivityAndGroup', 'dcmFloodlightActivityGroup', 'dcmFloodlightActivityGroupId', 'dcmFloodlightActivityId', 'dcmFloodlightAdvertiserId', 'dcmFloodlightSpotId', 'dcmLastEventAd', 'dcmLastEventAdId', 'dcmLastEventAdType', 'dcmLastEventAdTypeId', 'dcmLastEventAdvertiser', 'dcmLastEventAdvertiserId', 'dcmLastEventAttributionType', 'dcmLastEventCampaign', 'dcmLastEventCampaignId', 'dcmLastEventCreativeId', 'dcmLastEventCreative', 'dcmLastEventRenderingId', 'dcmLastEventCreativeType', 'dcmLastEventCreativeTypeId', 'dcmLastEventCreativeVersion', 'dcmLastEventSite', 'dcmLastEventSiteId', 'dcmLastEventSitePlacement', 'dcmLastEventSitePlacementId', 'dcmLastEventSpotId', 'landingContentGroup1', 'landingContentGroup2', 'landingContentGroup3', 'landingContentGroup4', 'landingContentGroup5', 'previousContentGroup1', 'previousContentGroup2', 'previousContentGroup3', 'previousContentGroup4', 'previousContentGroup5', 'contentGroup1', 'contentGroup2', 'contentGroup3', 'contentGroup4', 'contentGroup5', 'userAgeBracket', 'userGender', 'interestOtherCategory', 'interestAffinityCategory', 'interestInMarketCategory', 'dfpLineItemId', 'dfpLineItemName', 'acquisitionCampaign', 'acquisitionMedium', 'acquisitionSource', 'acquisitionSourceMedium', 'acquisitionTrafficChannel', 'browserSize', 'campaignCode', 'channelGrouping', 'checkoutOptions', 'cityId', 'cohort', 'cohortNthDay', 'cohortNthMonth', 'cohortNthWeek', 'continentId', 'countryIsoCode', 'dataSource', 'dbmClickAdvertiser', 'dbmClickAdvertiserId', 'dbmClickCreativeId', 'dbmClickExchange', 'dbmClickExchangeId', 'dbmClickInsertionOrder', 'dbmClickInsertionOrderId', 'dbmClickLineItem', 'dbmClickLineItemId', 'dbmClickSite', 'dbmClickSiteId', 'dbmLastEventAdvertiser', 'dbmLastEventAdvertiserId', 'dbmLastEventCreativeId', 'dbmLastEventExchange', 'dbmLastEventExchangeId', 'dbmLastEventInsertionOrder', 'dbmLastEventInsertionOrderId', 'dbmLastEventLineItem', 'dbmLastEventLineItemId', 'dbmLastEventSite', 'dbmLastEventSiteId', 'dsAdGroup', 'dsAdGroupId', 'dsAdvertiser', 'dsAdvertiserId', 'dsAgency', 'dsAgencyId', 'dsCampaign', 'dsCampaignId', 'dsEngineAccount', 'dsEngineAccountId', 'dsKeyword', 'dsKeywordId', 'experimentCombination', 'experimentName', 'internalPromotionCreative', 'internalPromotionId', 'internalPromotionName', 'internalPromotionPosition', 'isTrueViewVideoAd', 'metroId', 'nthHour', 'orderCouponCode', 'productBrand', 'productCategoryHierarchy', 'productCategoryLevel1', 'productCategoryLevel2', 'productCategoryLevel3', 'productCategoryLevel4', 'productCategoryLevel5', 'productCouponCode', 'productListName', 'productListPosition', 'productVariant', 'regionId', 'regionIsoCode', 'shoppingStage', 'subContinentCode']
    return render(request, 'data_report.html', {
        "dimensions": dimensions,
        "metrics": metrics,
        "img": "fb.svg",
        "labels": ["Total Page Likes", "Total Page Views", "Page Impressions", "Page Reach"],
        "values": [100, 100, 100, 100]
    })


@register.inclusion_tag('report_main.html', takes_context=True)
def analytics(context, next=None):

    ANALYTICS_CREDENTIALS_JSON = 'static/rfm360-c455b2faa813.json'
    ANALYTICS_VIEW_ID = '240348860'

    # The scope for the OAuth2 request.
    SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'

    # The location of the key file with the key data.
    KEY_FILEPATH = 'static/rfm360-c455b2faa813.json'

    # Load the key file's private data.
    with open(KEY_FILEPATH) as key_file:
        _key_data = json.load(key_file)
    # Construct a credentials objects from the key data and OAuth2 scope.
    _credentials = SignedJwtAssertionCredentials(
        _key_data['client_email'], _key_data['private_key'], SCOPE)
    return {
        'token': _credentials.get_access_token().access_token,
        'view_id': ANALYTICS_VIEW_ID
    }
# Create your views here.


@allowed_user(app_name='dashboard')
def Report_Main(request):
    print('Session : ',request.session['username'])
    print('Session_company: ',request.session['company'])
    income_list = UserIncome.objects.filter(owner=request.user)
    all_earnings = 0
    for income in income_list:
        all_earnings += income.amount
    print("all earnings=", all_earnings)
    visited_list = visited.objects.filter(
        companyId=request.user.profile.company.company_uuid)
    page_views = 0
    for visitor in visited_list:
        page_views += visitor.times_visited
    print("page views=", page_views)
    task_list = Task.objects.filter(creator_id=request.user.id)
    tasks = 0
    pendind_tasks = 0
    for task in task_list:
        tasks += 1
        if task.status.name != "Finished":
            pendind_tasks += 1
    print("tasks=", tasks)
    print("pending tasks=", pendind_tasks)
    projects_list = ProjectProfile.objects.filter(creator_id=request.user)
    latest_projects = []
    projects = 0
    for project in projects_list:
        projects += 1
    for i in range(projects-1, max(projects-5, -1), -1):
        latest_projects.append(projects_list[i])
    print("latest projects=", latest_projects)
    latest_tasks = []
    for i in range(tasks-1, max(tasks-5, -1), -1):
        try:
            task_list[i].assign_to = task_list[i].assign_to.split("'")[1]
        except:
            pass
        latest_tasks.append(task_list[i])
    print("latest tasks=", latest_tasks)
    customers_list = AddCustomer.objects.filter(user=request.user.id)
    customers = 0
    for customer in customers_list:
        customers += 1
    print("customers=",customers)
    proposals_list = Proposal.objects.filter(creator_id=request.user.id)
    proposals = 0
    pending_proposals = 0
    accepted_proposals = 0
    for proposal in proposals_list:
        proposal_status = ProposalStatus.objects.filter(proposal_id=proposal.id)
        proposals += 1
        if proposal_status[0].status == "accepted": accepted_proposals += 1
        else: pending_proposals += 1
    print("proposals=",proposals)
    print("accepted_proposals=",accepted_proposals)
    print("pending_proposals=",pending_proposals)
    income_list = UserIncome.objects.filter(owner=request.user)
    source_dict = {}
    for income in income_list:
        if income.source in source_dict:
            source_dict[income.source] += income.amount
        else:
            source_dict[income.source] = income.amount
    source_labels = []
    source_graph = []
    for source in source_dict:
        source_labels.append(source)
        source_graph.append(source_dict[source])
    print(source_labels, source_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for income in income_list:
        if income.date.month in date_dict:
            date_dict[income.date.month] += income.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    expense_list = Expense.objects.filter(owner=request.user)
    category_dict = {}
    for expense in expense_list:
        if expense.category in category_dict:
            category_dict[expense.category] += expense.amount
        else:
            category_dict[expense.category] = expense.amount
    category_labels = []
    category_graph = []
    for category in category_dict:
        category_labels.append(category)
        category_graph.append(category_dict[category])
    print(category_labels, category_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for expense in expense_list:
        if expense.date.month in date_dict:
            date_dict[expense.date.month] += expense.amount
    date_labels2 = []
    date_graph2 = []
    for date in date_dict:
        date_labels2.append(month_dict[date])
        date_graph2.append(date_dict[date])
    print(date_labels2, date_graph2)
    try:
        preference = UserPreference.objects.get(user=request.user)
        currency = preference.currency.split("-")[0].strip()
        print("currence=",currency)
    except:
        currency = ''
    return render(request, "report_main.html", {
        "all_earnings": all_earnings,
        "page_views": page_views,
        "tasks": tasks,
        "pending_tasks": pendind_tasks,
        "latest_projects": latest_projects,
        "latest_tasks": latest_tasks,
        "customers": customers,
        "proposals": proposals,
        "accepted_proposals": accepted_proposals,
        "pending_proposals": pending_proposals,
        "source_labels": source_labels,
        "source_graph": source_graph,
        "date_labels": date_labels,
        "date_graph": date_graph,
        "category_labels": category_labels,
        "category_graph": category_graph,
        "date_labels2": date_labels2,
        "date_graph2": date_graph2,
        "currency": currency
    })

def email_report(request): 
    email_list = MailStatus.objects.all()
    status_dict = {}
    for email in email_list:
        if email.status in status_dict:
            status_dict[email.status] += 1
        else:
            status_dict[email.status] = 1
    status_labels = []
    status_graph = []
    for status in status_dict:
        status_labels.append(status)
        status_graph.append(status_dict[status])
    print(status_labels, status_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for email in email_list:
        if email.timestamp.month in date_dict:
            date_dict[email.timestamp.month] += 1
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "email_report.html", {
        "status_labels": status_labels,
        "status_graph": status_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })
        


def add_client(request):
    return render(request, "add_client.html")


def integrations(request):
    integrations = Integrations.objects.filter(user=request.user)
    analytics_integrated = 0
    for integration in integrations:
        if integration.integration == "analytics":
            analytics_integrated = 1
    return render(request, "add_integration.html", {
        "analytics_integrated": analytics_integrated
    })


def task_report(request):
    task_list = Task.objects.filter(creator_id=request.user.id)
    priority_graph = [0, 0, 0, 0, 0]
    
    projects_dict = {}
    for task in task_list:
        project = str(task.related_to)
        if project in projects_dict:
            projects_dict[project] += 1
        else:
            projects_dict[project] = 1
    project_graph = []
    project_labels = []
    for project in projects_dict:
        project_labels.append(project)
        project_graph.append(projects_dict[project])
    print(project_labels, project_graph)
    return render(request, "task_report.html",
                  {"priority_graph": priority_graph,
                   "project_labels": project_labels,
                   "project_graph": project_graph})


def income_report(request):
    income_list = UserIncome.objects.filter(owner=request.user)
    source_dict = {}
    for income in income_list:
        if income.source in source_dict:
            source_dict[income.source] += income.amount
        else:
            source_dict[income.source] = income.amount
    source_labels = []
    source_graph = []
    for source in source_dict:
        source_labels.append(source)
        source_graph.append(source_dict[source])
    print(source_labels, source_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for income in income_list:
        if income.date.month in date_dict:
            date_dict[income.date.month] += income.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "income_report.html", {
        "source_labels": source_labels,
        "source_graph": source_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })

def expense_report(request):
    expense_list = Expense.objects.filter(owner=request.user)
    category_dict = {}
    for expense in expense_list:
        if expense.category in category_dict:
            category_dict[expense.category] += expense.amount
        else:
            category_dict[expense.category] = expense.amount
    category_labels = []
    category_graph = []
    for category in category_dict:
        category_labels.append(category)
        category_graph.append(category_dict[category])
    print(category_labels, category_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for expense in expense_list:
        if expense.date.month in date_dict:
            date_dict[expense.date.month] += expense.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "expense_report.html", {
        "category_labels": category_labels,
        "category_graph": category_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })


def visited_report(visited_list):
    country_dict = {}
    region_dict = {}
    device_dict = {}
    for visitor in visited_list:
        if visitor.country in country_dict:
            country_dict[visitor.country] += 1
        else:
            country_dict[visitor.country] = 1
        if visitor.region in region_dict:
            region_dict[visitor.region] += 1
        else:
            region_dict[visitor.region] = 1
        if visitor.device_type in device_dict:
            device_dict[visitor.device_type] += 1
        else:
            device_dict[visitor.device_type] = 1
    country_labels = []
    country_graph = []
    for country in country_dict:
        country_labels.append(country)
        country_graph.append(country_dict[country])
    region_labels = []
    region_graph = []
    for region in region_dict:
        region_labels.append(region)
        region_graph.append(region_dict[region])
    device_labels = []
    device_graph = []
    for device in device_dict:
        device_labels.append(device)
        device_graph.append(device_dict[device])
    print(country_labels, country_graph)
    print(region_labels, region_graph)
    print(device_labels, device_graph)
    pages_dict = {}
    for visitor in visited_list:
        for page in visitor.pages_visited:
            if page in pages_dict:
                pages_dict[page] += visitor.pages_visited[page]
            else:
                pages_dict[page] = visitor.pages_visited[page]
    pages_labels = []
    pages_graph = []
    for pages in pages_dict:
        pages_labels.append(pages)
        pages_graph.append(pages_dict[pages])
    print(pages_labels, pages_graph)
    return {
        "country_labels": country_labels,
        "country_graph": country_graph,
        "region_labels": region_labels,
        "region_graph": region_graph,
        "device_labels": device_labels,
        "device_graph": device_graph,
        "pages_labels": pages_labels,
        "pages_graph": pages_graph,
    }


def leads_report(request):
    leads_list = Leads.objects.all()
    visited_list = []
    for leads in leads_list:
        if leads.visited.companyId == request.user.profile.company.company_uuid:
            visited_list.append(leads.visited)
    return render(request, "leads_report.html", visited_report(visited_list))


def deals_report(request):
    deals_list = Deals.objects.all()
    visited_list = []
    for deals in deals_list:
        if deals.leads.visited.companyId == request.user.profile.company.company_uuid:
            visited_list.append(deals.leads.visited)
    return render(request, "deals_report.html", visited_report(visited_list))

def email_report(request): 
    email_list = MailStatus.objects.all()
    status_dict = {}
    for email in email_list:
        if email.status in status_dict:
            status_dict[email.status] += 1
        else:
            status_dict[email.status] = 1
    status_labels = []
    status_graph = []
    for status in status_dict:
        status_labels.append(status)
        status_graph.append(status_dict[status])
    print(status_labels, status_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for email in email_list:
        if email.timestamp.month in date_dict:
            date_dict[email.timestamp.month] += 1
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "email_report.html", {
        "status_labels": status_labels,
        "status_graph": status_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })

from django.shortcuts import render

import json
#from oauth2client.client import SignedJwtAssertionCredentials

from django import template
from chatapp.decorators import allowed_user
from Projects.models import ProjectStatus, Task, ProjectProfile
from Finance.models import UserIncome, Expense, UserPreference
from chatapp.models import leads as Leads, deals as Deals, visited
from invoice.models import AddCustomer
from proposal.models import Proposal, ProposalStatus
from .models import integrations as Integrations
from campaigns.models import MailStatus
import datetime
from campaigns.models import MailStatus
register = template.Library()


def data_report(request):
    metrics= ['users', 'newUsers', 'percentNewSessions', '1dayUsers', '7dayUsers', '14dayUsers', '28dayUsers', '30dayUsers', 'sessions', 'bounces', 'bounceRate', 'sessionDuration', 'avgSessionDuration', 'organicSearches', 'impressions', 'adClicks', 'adCost', 'CPM', 'CPC', 'CTR', 'costPerTransaction', 'costPerGoalConversion', 'costPerConversion', 'RPC', 'ROAS', 'goal1Starts', 'goal2Starts', 'goal3Starts', 'goal4Starts', 'goal5Starts', 'goal6Starts', 'goal7Starts', 'goal8Starts', 'goal9Starts', 'goal10Starts', 'goal11Starts', 'goal12Starts', 'goal13Starts', 'goal14Starts', 'goal15Starts', 'goal16Starts', 'goal17Starts', 'goal18Starts', 'goal19Starts', 'goal20Starts', 'goalStartsAll', 'goal1Completions', 'goal2Completions', 'goal3Completions', 'goal4Completions', 'goal5Completions', 'goal6Completions', 'goal7Completions', 'goal8Completions', 'goal9Completions', 'goal10Completions', 'goal11Completions', 'goal12Completions', 'goal13Completions', 'goal14Completions', 'goal15Completions', 'goal16Completions', 'goal17Completions', 'goal18Completions', 'goal19Completions', 'goal20Completions', 'goalCompletionsAll', 'goal1Value', 'goal2Value', 'goal3Value', 'goal4Value', 'goal5Value', 'goal6Value', 'goal7Value', 'goal8Value', 'goal9Value', 'goal10Value', 'goal11Value', 'goal12Value', 'goal13Value', 'goal14Value', 'goal15Value', 'goal16Value', 'goal17Value', 'goal18Value', 'goal19Value', 'goal20Value', 'goalValueAll', 'goalValuePerSession', 'goal1ConversionRate', 'goal2ConversionRate', 'goal3ConversionRate', 'goal4ConversionRate', 'goal5ConversionRate', 'goal6ConversionRate', 'goal7ConversionRate', 'goal8ConversionRate', 'goal9ConversionRate', 'goal10ConversionRate', 'goal11ConversionRate', 'goal12ConversionRate', 'goal13ConversionRate', 'goal14ConversionRate', 'goal15ConversionRate', 'goal16ConversionRate', 'goal17ConversionRate', 'goal18ConversionRate', 'goal19ConversionRate', 'goal20ConversionRate', 'goalConversionRateAll', 'goal1Abandons', 'goal2Abandons', 'goal3Abandons', 'goal4Abandons', 'goal5Abandons', 'goal6Abandons', 'goal7Abandons', 'goal8Abandons', 'goal9Abandons', 'goal10Abandons', 'goal11Abandons', 'goal12Abandons', 'goal13Abandons', 'goal14Abandons', 'goal15Abandons', 'goal16Abandons', 'goal17Abandons', 'goal18Abandons', 'goal19Abandons', 'goal20Abandons', 'goalAbandonsAll', 'goal1AbandonRate', 'goal2AbandonRate', 'goal3AbandonRate', 'goal4AbandonRate', 'goal5AbandonRate', 'goal6AbandonRate', 'goal7AbandonRate', 'goal8AbandonRate', 'goal9AbandonRate', 'goal10AbandonRate', 'goal11AbandonRate', 'goal12AbandonRate', 'goal13AbandonRate', 'goal14AbandonRate', 'goal15AbandonRate', 'goal16AbandonRate', 'goal17AbandonRate', 'goal18AbandonRate', 'goal19AbandonRate', 'goal20AbandonRate', 'goalAbandonRateAll', 'pageValue', 'entrances', 'entranceRate', 'pageviews', 'pageviewsPerSession', 'contentGroupUniqueViews1', 'contentGroupUniqueViews2', 'contentGroupUniqueViews3', 'contentGroupUniqueViews4', 'contentGroupUniqueViews5', 'uniquePageviews', 'timeOnPage', 'avgTimeOnPage', 'exits', 'exitRate', 'searchResultViews', 'searchUniques', 'avgSearchResultViews', 'searchSessions', 'percentSessionsWithSearch', 'searchDepth', 'avgSearchDepth', 'searchRefinements', 'percentSearchRefinements', 'searchDuration', 'avgSearchDuration', 'searchExits', 'searchExitRate', 'searchGoal1ConversionRate', 'searchGoal2ConversionRate', 'searchGoal3ConversionRate', 'searchGoal4ConversionRate', 'searchGoal5ConversionRate', 'searchGoal6ConversionRate', 'searchGoal7ConversionRate', 'searchGoal8ConversionRate', 'searchGoal9ConversionRate', 'searchGoal10ConversionRate', 'searchGoal11ConversionRate', 'searchGoal12ConversionRate', 'searchGoal13ConversionRate', 'searchGoal14ConversionRate', 'searchGoal15ConversionRate', 'searchGoal16ConversionRate', 'searchGoal17ConversionRate', 'searchGoal18ConversionRate', 'searchGoal19ConversionRate', 'searchGoal20ConversionRate', 'searchGoalConversionRateAll', 'goalValueAllPerSearch', 'pageLoadTime', 'pageLoadSample', 'avgPageLoadTime', 'domainLookupTime', 'avgDomainLookupTime', 'pageDownloadTime', 'avgPageDownloadTime', 'redirectionTime', 'avgRedirectionTime', 'serverConnectionTime', 'avgServerConnectionTime', 'serverResponseTime', 'avgServerResponseTime', 'speedMetricsSample', 'domInteractiveTime', 'avgDomInteractiveTime', 'domContentLoadedTime', 'avgDomContentLoadedTime', 'domLatencyMetricsSample', 'screenviews', 'uniqueScreenviews', 'screenviewsPerSession', 'timeOnScreen', 'avgScreenviewDuration', 'totalEvents', 'uniqueDimensionCombinations', 'uniqueEvents', 'eventValue', 'avgEventValue', 'sessionsWithEvent', 'eventsPerSessionWithEvent', 'transactions', 'transactionsPerSession', 'transactionRevenue', 'revenuePerTransaction', 'transactionRevenuePerSession', 'transactionShipping', 'transactionTax', 'totalValue', 'itemQuantity', 'uniquePurchases', 'revenuePerItem', 'itemRevenue', 'itemsPerPurchase', 'localTransactionRevenue', 'localTransactionShipping', 'localTransactionTax', 'localItemRevenue', 'socialInteractions', 'uniqueSocialInteractions', 'socialInteractionsPerSession', 'userTimingValue', 'userTimingSample', 'avgUserTimingValue', 'exceptions', 'exceptionsPerScreenview', 'fatalExceptions', 'fatalExceptionsPerScreenview', 'metric1', 'metric2', 'metric3', 'metric4', 'metric5', 'metric6', 'metric7', 'metric8', 'metric9', 'metric10', 'metric11', 'metric12', 'metric13', 'metric14', 'metric15', 'metric16', 'metric17', 'metric18', 'metric19', 'metric20', 'dcmFloodlightQuantity', 'dcmFloodlightRevenue', 'adsenseRevenue', 'adsenseAdUnitsViewed', 'adsenseAdsViewed', 'adsenseAdsClicks', 'adsensePageImpressions', 'adsenseCTR', 'adsenseECPM', 'adsenseExits', 'adsenseViewableImpressionPercent', 'adsenseCoverage', 'totalPublisherImpressions', 'totalPublisherCoverage', 'totalPublisherMonetizedPageviews', 'totalPublisherImpressionsPerSession', 'totalPublisherViewableImpressionsPercent', 'totalPublisherClicks', 'totalPublisherCTR', 'totalPublisherRevenue', 'totalPublisherRevenuePer1000Sessions', 'totalPublisherECPM', 'adxImpressions', 'adxCoverage', 'adxMonetizedPageviews', 'adxImpressionsPerSession', 'adxViewableImpressionsPercent', 'adxClicks', 'adxCTR', 'adxRevenue', 'adxRevenuePer1000Sessions', 'adxECPM', 'dfpImpressions', 'dfpCoverage', 'dfpMonetizedPageviews', 'dfpImpressionsPerSession', 'dfpViewableImpressionsPercent', 'dfpClicks', 'dfpCTR', 'dfpRevenue', 'dfpRevenuePer1000Sessions', 'dfpECPM', 'backfillImpressions', 'backfillCoverage', 'backfillMonetizedPageviews', 'backfillImpressionsPerSession', 'backfillViewableImpressionsPercent', 'backfillClicks', 'backfillCTR', 'backfillRevenue', 'backfillRevenuePer1000Sessions', 'backfillECPM', 'buyToDetailRate', 'calcMetric_<NAME>', 'cartToDetailRate', 'cohortActiveUsers', 'cohortAppviewsPerUser', 'cohortAppviewsPerUserWithLifetimeCriteria', 'cohortGoalCompletionsPerUser', 'cohortGoalCompletionsPerUserWithLifetimeCriteria', 'cohortPageviewsPerUser', 'cohortPageviewsPerUserWithLifetimeCriteria', 'cohortRetentionRate', 'cohortRevenuePerUser', 'cohortRevenuePerUserWithLifetimeCriteria', 'cohortSessionDurationPerUser', 'cohortSessionDurationPerUserWithLifetimeCriteria', 'cohortSessionsPerUser', 'cohortSessionsPerUserWithLifetimeCriteria', 'cohortTotalUsers', 'cohortTotalUsersWithLifetimeCriteria', 'dbmCPA', 'dbmCPC', 'dbmCPM', 'dbmCTR', 'dbmClicks', 'dbmConversions', 'dbmCost', 'dbmImpressions', 'dbmROAS', 'dcmCPC', 'dcmCTR', 'dcmClicks', 'dcmCost', 'dcmImpressions', 'dcmROAS', 'dcmRPC', 'dsCPC', 'dsCTR', 'dsClicks', 'dsCost', 'dsImpressions', 'dsProfit', 'dsReturnOnAdSpend', 'dsRevenuePerClick', 'hits', 'internalPromotionCTR', 'internalPromotionClicks', 'internalPromotionViews', 'localProductRefundAmount', 'localRefundAmount', 'productAddsToCart', 'productCheckouts', 'productDetailViews', 'productListCTR', 'productListClicks', 'productListViews', 'productRefundAmount', 'productRefunds', 'productRemovesFromCart', 'productRevenuePerPurchase', 'quantityAddedToCart', 'quantityCheckedOut', 'quantityRefunded', 'quantityRemovedFromCart', 'refundAmount', 'revenuePerUser', 'sessionsPerUser', 'totalRefunds', 'transactionsPerUser']
    dimensions = ['userType', 'sessionCount', 'daysSinceLastSession', 'userDefinedValue', 'userBucket', 'sessionDurationBucket', 'referralPath', 'fullReferrer', 'campaign', 'source', 'medium', 'sourceMedium', 'keyword', 'adContent', 'socialNetwork', 'hasSocialSourceReferral', 'adGroup', 'adSlot', 'adDistributionNetwork', 'adMatchType', 'adKeywordMatchType', 'adMatchedQuery', 'adPlacementDomain', 'adPlacementUrl', 'adFormat', 'adTargetingType', 'adTargetingOption', 'adDisplayUrl', 'adDestinationUrl', 'adwordsCustomerID', 'adwordsCampaignID', 'adwordsAdGroupID', 'adwordsCreativeID', 'adwordsCriteriaID', 'adQueryWordCount', 'goalCompletionLocation', 'goalPreviousStep1', 'goalPreviousStep2', 'goalPreviousStep3', 'browser', 'browserVersion', 'operatingSystem', 'operatingSystemVersion', 'mobileDeviceBranding', 'mobileDeviceModel', 'mobileInputSelector', 'mobileDeviceInfo', 'mobileDeviceMarketingName', 'deviceCategory', 'continent', 'subContinent', 'country', 'region', 'metro', 'city', 'latitude', 'longitude', 'networkDomain', 'networkLocation', 'flashVersion', 'javaEnabled', 'language', 'screenColors', 'sourcePropertyDisplayName', 'sourcePropertyTrackingId', 'screenResolution', 'hostname', 'pagePath', 'pagePathLevel1', 'pagePathLevel2', 'pagePathLevel3', 'pagePathLevel4', 'pageTitle', 'landingPagePath', 'secondPagePath', 'exitPagePath', 'previousPagePath', 'pageDepth', 'searchUsed', 'searchKeyword', 'searchKeywordRefinement', 'searchCategory', 'searchStartPage', 'searchDestinationPage', 'searchAfterDestinationPage', 'appInstallerId', 'appVersion', 'appName', 'appId', 'screenName', 'screenDepth', 'landingScreenName', 'exitScreenName', 'eventCategory', 'eventAction', 'eventLabel', 'transactionId', 'affiliation', 'sessionsToTransaction', 'daysToTransaction', 'productSku', 'productName', 'productCategory', 'currencyCode', 'socialInteractionNetwork', 'socialInteractionAction', 'socialInteractionNetworkAction', 'socialInteractionTarget', 'socialEngagementType', 'userTimingCategory', 'userTimingLabel', 'userTimingVariable', 'exceptionDescription', 'experimentId', 'experimentVariant', 'dimension1', 'dimension2', 'dimension3', 'dimension4', 'dimension5', 'dimension6', 'dimension7', 'dimension8', 'dimension9', 'dimension10', 'dimension11', 'dimension12', 'dimension13', 'dimension14', 'dimension15', 'dimension16', 'dimension17', 'dimension18', 'dimension19', 'dimension20', 'customVarName1', 'customVarName2', 'customVarName3', 'customVarName4', 'customVarName5', 'customVarValue1', 'customVarValue2', 'customVarValue3', 'customVarValue4', 'customVarValue5', 'date', 'year', 'month', 'week', 'day', 'hour', 'minute', 'nthMonth', 'nthWeek', 'nthDay', 'nthMinute', 'dayOfWeek', 'dayOfWeekName', 'dateHour', 'dateHourMinute', 'yearMonth', 'yearWeek', 'isoWeek', 'isoYear', 'isoYearIsoWeek', 'dcmClickAd', 'dcmClickAdId', 'dcmClickAdType', 'dcmClickAdTypeId', 'dcmClickAdvertiser', 'dcmClickAdvertiserId', 'dcmClickCampaign', 'dcmClickCampaignId', 'dcmClickCreativeId', 'dcmClickCreative', 'dcmClickRenderingId', 'dcmClickCreativeType', 'dcmClickCreativeTypeId', 'dcmClickCreativeVersion', 'dcmClickSite', 'dcmClickSiteId', 'dcmClickSitePlacement', 'dcmClickSitePlacementId', 'dcmClickSpotId', 'dcmFloodlightActivity', 'dcmFloodlightActivityAndGroup', 'dcmFloodlightActivityGroup', 'dcmFloodlightActivityGroupId', 'dcmFloodlightActivityId', 'dcmFloodlightAdvertiserId', 'dcmFloodlightSpotId', 'dcmLastEventAd', 'dcmLastEventAdId', 'dcmLastEventAdType', 'dcmLastEventAdTypeId', 'dcmLastEventAdvertiser', 'dcmLastEventAdvertiserId', 'dcmLastEventAttributionType', 'dcmLastEventCampaign', 'dcmLastEventCampaignId', 'dcmLastEventCreativeId', 'dcmLastEventCreative', 'dcmLastEventRenderingId', 'dcmLastEventCreativeType', 'dcmLastEventCreativeTypeId', 'dcmLastEventCreativeVersion', 'dcmLastEventSite', 'dcmLastEventSiteId', 'dcmLastEventSitePlacement', 'dcmLastEventSitePlacementId', 'dcmLastEventSpotId', 'landingContentGroup1', 'landingContentGroup2', 'landingContentGroup3', 'landingContentGroup4', 'landingContentGroup5', 'previousContentGroup1', 'previousContentGroup2', 'previousContentGroup3', 'previousContentGroup4', 'previousContentGroup5', 'contentGroup1', 'contentGroup2', 'contentGroup3', 'contentGroup4', 'contentGroup5', 'userAgeBracket', 'userGender', 'interestOtherCategory', 'interestAffinityCategory', 'interestInMarketCategory', 'dfpLineItemId', 'dfpLineItemName', 'acquisitionCampaign', 'acquisitionMedium', 'acquisitionSource', 'acquisitionSourceMedium', 'acquisitionTrafficChannel', 'browserSize', 'campaignCode', 'channelGrouping', 'checkoutOptions', 'cityId', 'cohort', 'cohortNthDay', 'cohortNthMonth', 'cohortNthWeek', 'continentId', 'countryIsoCode', 'dataSource', 'dbmClickAdvertiser', 'dbmClickAdvertiserId', 'dbmClickCreativeId', 'dbmClickExchange', 'dbmClickExchangeId', 'dbmClickInsertionOrder', 'dbmClickInsertionOrderId', 'dbmClickLineItem', 'dbmClickLineItemId', 'dbmClickSite', 'dbmClickSiteId', 'dbmLastEventAdvertiser', 'dbmLastEventAdvertiserId', 'dbmLastEventCreativeId', 'dbmLastEventExchange', 'dbmLastEventExchangeId', 'dbmLastEventInsertionOrder', 'dbmLastEventInsertionOrderId', 'dbmLastEventLineItem', 'dbmLastEventLineItemId', 'dbmLastEventSite', 'dbmLastEventSiteId', 'dsAdGroup', 'dsAdGroupId', 'dsAdvertiser', 'dsAdvertiserId', 'dsAgency', 'dsAgencyId', 'dsCampaign', 'dsCampaignId', 'dsEngineAccount', 'dsEngineAccountId', 'dsKeyword', 'dsKeywordId', 'experimentCombination', 'experimentName', 'internalPromotionCreative', 'internalPromotionId', 'internalPromotionName', 'internalPromotionPosition', 'isTrueViewVideoAd', 'metroId', 'nthHour', 'orderCouponCode', 'productBrand', 'productCategoryHierarchy', 'productCategoryLevel1', 'productCategoryLevel2', 'productCategoryLevel3', 'productCategoryLevel4', 'productCategoryLevel5', 'productCouponCode', 'productListName', 'productListPosition', 'productVariant', 'regionId', 'regionIsoCode', 'shoppingStage', 'subContinentCode']
    return render(request, 'data_report.html', {
        "dimensions": dimensions,
        "metrics": metrics,
        "img": "fb.svg",
        "labels": ["Total Page Likes", "Total Page Views", "Page Impressions", "Page Reach"],
        "values": [100, 100, 100, 100]
    })


@register.inclusion_tag('report_main.html', takes_context=True)
def analytics(context, next=None):

    ANALYTICS_CREDENTIALS_JSON = 'static/rfm360-c455b2faa813.json'
    ANALYTICS_VIEW_ID = '240348860'

    # The scope for the OAuth2 request.
    SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'

    # The location of the key file with the key data.
    KEY_FILEPATH = 'static/rfm360-c455b2faa813.json'

    # Load the key file's private data.
    with open(KEY_FILEPATH) as key_file:
        _key_data = json.load(key_file)
    # Construct a credentials objects from the key data and OAuth2 scope.
    _credentials = SignedJwtAssertionCredentials(
        _key_data['client_email'], _key_data['private_key'], SCOPE)
    return {
        'token': _credentials.get_access_token().access_token,
        'view_id': ANALYTICS_VIEW_ID
    }
# Create your views here.


@allowed_user(app_name='dashboard')
def Report_Main(request):
    print('Session : ',request.session['username'])
    print('Session_company: ',request.session['company'])
    income_list = UserIncome.objects.filter(owner=request.user)
    all_earnings = 0
    for income in income_list:
        all_earnings += income.amount
    print("all earnings=", all_earnings)
    visited_list = visited.objects.filter(
        companyId=request.user.profile.company.company_uuid)
    page_views = 0
    for visitor in visited_list:
        page_views += visitor.times_visited
    print("page views=", page_views)
    task_list = Task.objects.filter(creator_id=request.user.id)
    tasks = 0
    pendind_tasks = 0
    for task in task_list:
        tasks += 1
        if task.status.name != "Finished":
            pendind_tasks += 1
    print("tasks=", tasks)
    print("pending tasks=", pendind_tasks)
    projects_list = ProjectProfile.objects.filter(creator_id=request.user)
    latest_projects = []
    projects = 0
    for project in projects_list:
        projects += 1
    for i in range(projects-1, max(projects-5, -1), -1):
        latest_projects.append(projects_list[i])
    print("latest projects=", latest_projects)
    latest_tasks = []
    for i in range(tasks-1, max(tasks-5, -1), -1):
        try:
            task_list[i].assign_to = task_list[i].assign_to.split("'")[1]
        except:
            pass
        latest_tasks.append(task_list[i])
    print("latest tasks=", latest_tasks)
    customers_list = AddCustomer.objects.filter(user=request.user.id)
    customers = 0
    for customer in customers_list:
        customers += 1
    print("customers=",customers)
    proposals_list = Proposal.objects.filter(creator_id=request.user.id)
    proposals = 0
    pending_proposals = 0
    accepted_proposals = 0
    for proposal in proposals_list:
        proposal_status = ProposalStatus.objects.filter(proposal_id=proposal.id)
        proposals += 1
        if proposal_status[0].status == "accepted": accepted_proposals += 1
        else: pending_proposals += 1
    print("proposals=",proposals)
    print("accepted_proposals=",accepted_proposals)
    print("pending_proposals=",pending_proposals)
    income_list = UserIncome.objects.filter(owner=request.user)
    source_dict = {}
    for income in income_list:
        if income.source in source_dict:
            source_dict[income.source] += income.amount
        else:
            source_dict[income.source] = income.amount
    source_labels = []
    source_graph = []
    for source in source_dict:
        source_labels.append(source)
        source_graph.append(source_dict[source])
    print(source_labels, source_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for income in income_list:
        if income.date.month in date_dict:
            date_dict[income.date.month] += income.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    expense_list = Expense.objects.filter(owner=request.user)
    category_dict = {}
    for expense in expense_list:
        if expense.category in category_dict:
            category_dict[expense.category] += expense.amount
        else:
            category_dict[expense.category] = expense.amount
    category_labels = []
    category_graph = []
    for category in category_dict:
        category_labels.append(category)
        category_graph.append(category_dict[category])
    print(category_labels, category_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for expense in expense_list:
        if expense.date.month in date_dict:
            date_dict[expense.date.month] += expense.amount
    date_labels2 = []
    date_graph2 = []
    for date in date_dict:
        date_labels2.append(month_dict[date])
        date_graph2.append(date_dict[date])
    print(date_labels2, date_graph2)
    try:
        preference = UserPreference.objects.get(user=request.user)
        currency = preference.currency.split("-")[0].strip()
        print("currence=",currency)
    except:
        currency = ''
    return render(request, "report_main.html", {
        "all_earnings": all_earnings,
        "page_views": page_views,
        "tasks": tasks,
        "pending_tasks": pendind_tasks,
        "latest_projects": latest_projects,
        "latest_tasks": latest_tasks,
        "customers": customers,
        "proposals": proposals,
        "accepted_proposals": accepted_proposals,
        "pending_proposals": pending_proposals,
        "source_labels": source_labels,
        "source_graph": source_graph,
        "date_labels": date_labels,
        "date_graph": date_graph,
        "category_labels": category_labels,
        "category_graph": category_graph,
        "date_labels2": date_labels2,
        "date_graph2": date_graph2,
        "currency": currency
    })

def email_report(request): 
    email_list = MailStatus.objects.all()
    status_dict = {}
    for email in email_list:
        if email.status in status_dict:
            status_dict[email.status] += 1
        else:
            status_dict[email.status] = 1
    status_labels = []
    status_graph = []
    for status in status_dict:
        status_labels.append(status)
        status_graph.append(status_dict[status])
    print(status_labels, status_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for email in email_list:
        if email.timestamp.month in date_dict:
            date_dict[email.timestamp.month] += 1
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "email_report.html", {
        "status_labels": status_labels,
        "status_graph": status_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })
        


def add_client(request):
    return render(request, "add_client.html")


def integrations(request):
    integrations = Integrations.objects.filter(user=request.user)
    analytics_integrated = 0
    for integration in integrations:
        if integration.integration == "analytics":
            analytics_integrated = 1
    return render(request, "add_integration.html", {
        "analytics_integrated": analytics_integrated
    })


def task_report(request):
    task_list = Task.objects.filter(creator_id=request.user.id)
    priority_graph = [0, 0, 0, 0, 0]
    
    projects_dict = {}
    for task in task_list:
        project = str(task.related_to)
        if project in projects_dict:
            projects_dict[project] += 1
        else:
            projects_dict[project] = 1
    project_graph = []
    project_labels = []
    for project in projects_dict:
        project_labels.append(project)
        project_graph.append(projects_dict[project])
    print(project_labels, project_graph)
    return render(request, "task_report.html",
                  {"priority_graph": priority_graph,
                   "project_labels": project_labels,
                   "project_graph": project_graph})


def income_report(request):
    income_list = UserIncome.objects.filter(owner=request.user)
    source_dict = {}
    for income in income_list:
        if income.source in source_dict:
            source_dict[income.source] += income.amount
        else:
            source_dict[income.source] = income.amount
    source_labels = []
    source_graph = []
    for source in source_dict:
        source_labels.append(source)
        source_graph.append(source_dict[source])
    print(source_labels, source_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for income in income_list:
        if income.date.month in date_dict:
            date_dict[income.date.month] += income.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "income_report.html", {
        "source_labels": source_labels,
        "source_graph": source_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })

def expense_report(request):
    expense_list = Expense.objects.filter(owner=request.user)
    category_dict = {}
    for expense in expense_list:
        if expense.category in category_dict:
            category_dict[expense.category] += expense.amount
        else:
            category_dict[expense.category] = expense.amount
    category_labels = []
    category_graph = []
    for category in category_dict:
        category_labels.append(category)
        category_graph.append(category_dict[category])
    print(category_labels, category_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for expense in expense_list:
        if expense.date.month in date_dict:
            date_dict[expense.date.month] += expense.amount
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "expense_report.html", {
        "category_labels": category_labels,
        "category_graph": category_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })


def visited_report(visited_list):
    country_dict = {}
    region_dict = {}
    device_dict = {}
    for visitor in visited_list:
        if visitor.country in country_dict:
            country_dict[visitor.country] += 1
        else:
            country_dict[visitor.country] = 1
        if visitor.region in region_dict:
            region_dict[visitor.region] += 1
        else:
            region_dict[visitor.region] = 1
        if visitor.device_type in device_dict:
            device_dict[visitor.device_type] += 1
        else:
            device_dict[visitor.device_type] = 1
    country_labels = []
    country_graph = []
    for country in country_dict:
        country_labels.append(country)
        country_graph.append(country_dict[country])
    region_labels = []
    region_graph = []
    for region in region_dict:
        region_labels.append(region)
        region_graph.append(region_dict[region])
    device_labels = []
    device_graph = []
    for device in device_dict:
        device_labels.append(device)
        device_graph.append(device_dict[device])
    print(country_labels, country_graph)
    print(region_labels, region_graph)
    print(device_labels, device_graph)
    pages_dict = {}
    for visitor in visited_list:
        for page in visitor.pages_visited:
            if page in pages_dict:
                pages_dict[page] += visitor.pages_visited[page]
            else:
                pages_dict[page] = visitor.pages_visited[page]
    pages_labels = []
    pages_graph = []
    for pages in pages_dict:
        pages_labels.append(pages)
        pages_graph.append(pages_dict[pages])
    print(pages_labels, pages_graph)
    return {
        "country_labels": country_labels,
        "country_graph": country_graph,
        "region_labels": region_labels,
        "region_graph": region_graph,
        "device_labels": device_labels,
        "device_graph": device_graph,
        "pages_labels": pages_labels,
        "pages_graph": pages_graph,
    }


def leads_report(request):
    leads_list = Leads.objects.all()
    visited_list = []
    for leads in leads_list:
        if leads.visited.companyId == request.user.profile.company.company_uuid:
            visited_list.append(leads.visited)
    return render(request, "leads_report.html", visited_report(visited_list))


def deals_report(request):
    deals_list = Deals.objects.all()
    visited_list = []
    for deals in deals_list:
        if deals.leads.visited.companyId == request.user.profile.company.company_uuid:
            visited_list.append(deals.leads.visited)
    return render(request, "deals_report.html", visited_report(visited_list))

def email_report(request): 
    email_list = MailStatus.objects.all()
    status_dict = {}
    for email in email_list:
        if email.status in status_dict:
            status_dict[email.status] += 1
        else:
            status_dict[email.status] = 1
    status_labels = []
    status_graph = []
    for status in status_dict:
        status_labels.append(status)
        status_graph.append(status_dict[status])
    print(status_labels, status_graph)
    date = datetime.datetime.now()
    date_dict = {}
    for i in range(6):
        date_dict[(date.month-5+i) % 12] = 0
    for email in email_list:
        if email.timestamp.month in date_dict:
            date_dict[email.timestamp.month] += 1
    month_dict = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    date_labels = []
    date_graph = []
    for date in date_dict:
        date_labels.append(month_dict[date])
        date_graph.append(date_dict[date])
    print(date_labels, date_graph)
    return render(request, "email_report.html", {
        "status_labels": status_labels,
        "status_graph": status_graph,
        "date_labels": date_labels,
        "date_graph": date_graph
    })

