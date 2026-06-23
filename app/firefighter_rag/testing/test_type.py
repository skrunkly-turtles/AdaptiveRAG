import pytest 
import demo
import demo_v2


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text, expected_sources", [
    # =========================
    # [7] Current / latest (15)
    # =========================
    ("What is her heart rate right now?", [7]),
    ("Are they in critical condition right now?", [7]),
    ("What is his current oxygen saturation?", [7]),
    ("Show me the latest temperature reading.", [7]),
    ("What is her blood pressure currently?", [7]),
    ("What is the current elevation?", [7]),
    ("Give me the last heart rate measurement.", [7]),
    ("What is the latest O2 stat?", [7]),
    ("How fast is he moving right now?", [7]),
    ("What is the current respiration rate?", [7]),
    ("Is her temperature elevated currently?", [7]),
    ("What's the current battery level?", [7]),
    ("Show the latest location reading.", [7]),
    ("What was the last recorded pulse?", [7]),
    ("What time is it?", [7]),

    # =========================
    # [1] Recent summaries (15)
    # =========================
    ("What has her heart rate been recently?", [1]),
    ("Show the recent oxygen saturation trend.", [1]),
    ("What is the recent average temperature?", [1]),
    ("How has his elevation changed recently?", [1]),
    ("What was the pulse rate over the past minute?", [1]),
    ("Has her blood pressure increased recently?", [1]),
    ("Show recent respiration readings.", [1]),
    ("What is the short-term average O2 stat?", [1]),
    ("How stable has the temperature been recently?", [1]),
    ("What is the recent movement speed?", [1]),
    ("Show the recent humidity measurements.", [1]),
    ("Has the battery drained recently?", [1]),
    ("What is the recent altitude average?", [1]),
    ("How much has the pulse varied recently?", [1]),
    ("Show recent heart rate fluctuations.", [1]),

    # =========================
    # [7,1] Current vs recent (15)
    # =========================
    ("How does their current elevation compare to their elevation recently?", [7, 1]),
    ("Compare the current heart rate to the recent average.", [7, 1]),
    ("Current temperature versus recent temperature.", [7, 1]),
    ("How does the latest oxygen reading compare to recent readings?", [7, 1]),
    ("Compare current blood pressure with recent measurements.", [7, 1]),
    ("How is the current pulse compared to the recent trend?", [7, 1]),
    ("Current respiration rate versus recent respiration rate.", [7, 1]),
    ("How does current humidity compare to recent humidity?", [7, 1]),
    ("Compare the latest altitude to the recent average altitude.", [7, 1]),
    ("How is the current speed relative to recent speed?", [7, 1]),
    ("Compare current oxygen saturation to the recent average.", [7, 1]),
    ("Is the current temperature higher than it has been recently?", [7, 1]),
    ("How different is the latest pulse from recent readings?", [7, 1]),
    ("Compare the current ECG to recent ECG activity.", [7, 1]),
    ("How does the latest elevation compare with recent elevation data?", [7, 1]),

    # =========================
    # [7,2] Current vs all-time (15)
    # =========================
    ("How does current temperature compare to the all time minimum?", [7, 2]),
    ("Compare the current heart rate to the all-time average.", [7, 2]),
    ("How does the latest oxygen reading compare to the historical maximum?", [7, 2]),
    ("Current elevation versus all-time highest elevation.", [7, 2]),
    ("How is the current pulse compared to the overall average?", [7, 2]),
    ("Compare current blood pressure with the historical minimum.", [7, 2]),
    ("How does the latest temperature compare to the maximum so far?", [7, 2]),
    ("Current respiration rate versus all-time trend.", [7, 2]),
    ("How does the current humidity compare to historical averages?", [7, 2]),
    ("Compare the latest altitude to the all-time peak.", [7, 2]),
    ("How does current oxygen compare to the lowest ever recorded value?", [7, 2]),
    ("Is the current heart rate above the long-term average?", [7, 2]),
    ("Compare today's latest temperature to the historical average.", [7, 2]),
    ("How unusual is the current elevation compared to all recorded data?", [7, 2]),
    ("How does the latest pulse compare with the maximum pulse ever seen?", [7, 2]),

    # =========================
    # [2] All-time summaries (15)
    # =========================
    ("What is his average all time o2 stat?", [2]),
    ("What is the range of the temperature so far?", [2]),
    ("What is the all-time average heart rate?", [2]),
    ("Show the historical maximum temperature.", [2]),
    ("What is the minimum oxygen saturation ever recorded?", [2]),
    ("What is the overall trend in elevation?", [2]),
    ("Give me the average blood pressure.", [2]),
    ("What is the maximum pulse recorded so far?", [2]),
    ("Show the historical range of humidity.", [2]),
    ("What is the all-time highest altitude?", [2]),
    ("What is the overall respiration trend?", [2]),
    ("What is the average skin temperature?", [2]),
    ("Show the minimum heart rate ever measured.", [2]),
    ("What is the maximum movement speed recorded?", [2]),
    ("What has been the overall oxygen trend?", [2]),

    # =========================
    # [] Unrelated (10)
    # =========================
    ("Tell me a joke", []),
    ("Hello there", []),
    ("Good morning", []),
    ("What's your favorite movie?", []),
    ("Who won the World Cup?", []),
    ("Write me a poem about cats.", []),
    ("Do you like pizza?", []),
    ("What is the colour of the sky?", []),
    ("Can you recommend a book?", []),
    ("What's the capital of France?", []),

    # =========================
    # [1,2] Less-obvious (5)
    # =========================
    ("How does the recent average heart rate compare to the all-time average?", [1, 2]),
    ("Compare recent oxygen levels against historical norms.", [1, 2]),
    ("Is the last minute's temperature trend different from the overall trend?", [1, 2]),
    ("How does recent elevation compare with the all-time average elevation?", [1, 2]),
    ("Compare the recent pulse average to the historical average.", [1, 2]),

    # =========================
    # [0] Raw recent data (3)
    # =========================
    ("Show every heart rate reading from the last minute.", [0]),
    ("List all oxygen measurements from the past 60 seconds.", [0]),
    ("Plot raw temperature values from the last minute.", [0]),

    # =========================
    # [0,1] Raw + summary (2)
    # =========================
    ("Give the recent heart rate average and all readings from the last minute.", [0, 1]),
    ("Show recent temperature statistics and the underlying raw measurements.", [0, 1]),

    # =========================
    # Full histories (5)
    # =========================
    ("Plot every heart rate reading we have ever recorded.", [3]),
    ("Show the complete oxygen saturation history.", [4]),
    ("Export all temperature measurements.", [5]),
    ("Graph the full elevation dataset.", [6]),
    ("List every heart rate measurement ever recorded.", [3]),
])

async def test_routing_query(query_text, expected_sources):
    actual_sources = await demo_v2.type_of_query(query_text)
    assert sorted(expected_sources) in sorted(actual_sources), (
        f"\nQuery:    {query_text}"
        f"\nExpected: {expected_sources}"
        f"\nGot:      {actual_sources}"
    )

# async def test_routing_query(query_text, expected_type):
#     actual_type = await demo_v2.type_of_query(query_text)
#     assert actual_type == expected_type
