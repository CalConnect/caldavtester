##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##

"""
Verifier that checks the response of a free-busy-query.
"""

from pycalendar.calendar import PyCalendar
from pycalendar.exceptions import PyCalendarInvalidData
from xml.etree.ElementTree import ElementTree
from xml.parsers.expat import ExpatError
import StringIO

class Verifier(object):

    def verify(self, manager, uri, response, respdata, args): #@UnusedVariable

        # Must have status 200
        if response.status != 200:
            return False, "        HTTP Status Code Wrong: %d" % (response.status,)

        # Get expected FREEBUSY info
        users = args.get("attendee", [])
        busy = args.get("busy", [])
        tentative = args.get("tentative", [])
        unavailable = args.get("unavailable", [])

        # Extract each calendar-data object
        try:
            tree = ElementTree(file=StringIO.StringIO(respdata))
        except ExpatError:
            return False, "           Could not parse proper XML response\n"

        for calendar in tree.findall("./{urn:ietf:params:xml:ns:caldav}response/{urn:ietf:params:xml:ns:caldav}calendar-data"):
            # Parse data as calendar object
            try:
                calendar = PyCalendar.parseText(calendar.text)

                # Check for calendar
                if calendar is None:
                    raise ValueError("Not a calendar: %s" % (calendar,))

                # Only one component
                comps = calendar.getComponents("VFREEBUSY")
                if len(comps) != 1:
                    raise ValueError("Wrong number or unexpected components in calendar")

                # Must be VFREEBUSY
                fb = comps[0]

                    # Check for attendee value
                for attendee in fb.getProperties("ATTENDEE"):
                    if attendee.getValue().getValue() in users:
                        users.remove(attendee.getValue().getValue())
                        break
                else:
                    continue

                # Extract periods
                busyp = []
                tentativep = []
                unavailablep = []
                for fp in fb.getProperties("FREEBUSY"):
                    periods = fp.getValue().getValues()
                    # Convert start/duration to start/end
                    for i in range(len(periods)):
                        periods[i].getValue().setUseDuration(False)
                    # Check param
                    fbtype = "BUSY"
                    if fp.hasAttribute("FBTYPE"):
                        fbtype = fp.getAttributeValue("FBTYPE")
                    if fbtype == "BUSY":
                        busyp.extend(periods)
                    elif fbtype == "BUSY-TENTATIVE":
                        tentativep.extend(periods)
                    elif fbtype == "BUSY-UNAVAILABLE":
                        unavailablep.extend(periods)
                    else:
                        raise ValueError("Unknown FBTYPE: %s" % (fbtype,))

                # Set sizes must match
                if ((len(busy) != len(busyp)) or
                    (len(unavailable) != len(unavailablep)) or
                    (len(tentative) != len(tentativep))):
                    raise ValueError("Period list sizes do not match.")

                # Convert to string sets
                busy = set(busy)
                busyp = [x.getValue().getText() for x in busyp]
                busyp = set(busyp)
                tentative = set(tentative)
                tentativep = [x.getValue().getText() for x in tentativep]
                tentativep = set(tentativep)
                unavailable = set(unavailable)
                unavailablep = [x.getValue().getText() for x in unavailablep]
                unavailablep = set(unavailablep)

                # Compare all periods
                if len(busyp.symmetric_difference(busy)):
                    raise ValueError("Busy periods do not match")
                elif len(tentativep.symmetric_difference(tentative)):
                    raise ValueError("Busy-tentative periods do not match")
                elif len(unavailablep.symmetric_difference(unavailable)):
                    raise ValueError("Busy-unavailable periods do not match")

                break

            except PyCalendarInvalidData:
                return False, "        HTTP response data is not a calendar"
            except ValueError, txt:
                return False, "        HTTP response data is invalid: %s" % (txt,)

        if len(users):
            return False, "           Could not find attendee/calendar data in XML response\n"

        return True, ""
