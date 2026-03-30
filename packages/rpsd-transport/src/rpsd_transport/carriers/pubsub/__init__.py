# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""PubSub carriers for rpsd-transport."""

from rpsd_transport.carriers.pubsub.base import PubSubCarrier

__all__ = [
    "PubSubCarrier",
]

# Broker-specific carriers are imported explicitly to avoid
# requiring all broker dependencies:
#
#   from rpsd_transport.carriers.pubsub.kafka import (
#       KafkaPubSubCarrier,
#       KafkaCarrierOptions,
#   )
#
#   from rpsd_transport.carriers.pubsub.rabbitmq import (
#       RabbitMQPubSubCarrier,
#       RabbitMQCarrierOptions,
#   )
